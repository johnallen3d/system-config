#!/usr/bin/env python3
"""Build remote main in isolation; promote only tested, healthy Credits releases."""

from contextlib import closing
import fcntl
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request


HEALTH_URL = "http://127.0.0.1:3001/"
SERVICE = "credits.service"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def git(repository, *args):
    return subprocess.check_output(
        ["git", "--git-dir", str(repository), *args], text=True, timeout=120
    ).strip()


def link_release(link, release):
    pending = link.with_name(link.name + ".new")
    pending.unlink(missing_ok=True)
    pending.symlink_to(release)
    pending.replace(link)


def healthy(timeout=45):
    deadline = time.monotonic() + timeout
    # Never send loopback health checks to an inherited HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open(HEALTH_URL, timeout=2) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    return False


def control(action):
    run("systemctl", "--user", action, SERVICE, timeout=60)


def snapshot_database(database, snapshot):
    snapshot.unlink(missing_ok=True)
    if database.exists():
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(snapshot)) as target:
            with target:
                source.backup(target)


def restore_database(database, snapshot):
    # Called only after the backend has stopped. Restore schema as well as data.
    for suffix in ("-wal", "-shm"):
        Path(str(database) + suffix).unlink(missing_ok=True)
    if snapshot.exists():
        shutil.copyfile(snapshot, database)
    else:
        database.unlink(missing_ok=True)


def promote(state, release, check=healthy, service=control):
    current = state / "current"
    previous = current.resolve() if current.is_symlink() else None
    database = state / "cache.sqlite3"
    snapshot = release / "before.sqlite3"
    service("stop")
    try:
        snapshot_database(database, snapshot)
    except Exception:
        if previous:
            service("start")
        raise
    try:
        link_release(current, release)
        service("reset-failed")
        service("start")
        if not check():
            raise RuntimeError("new release failed its HTTP health check")
    except Exception:
        # Restore the pre-migration database before bringing the old binary back.
        service("stop")
        restore_database(database, snapshot)
        if previous:
            link_release(current, previous)
            service("reset-failed")
            service("start")
            if not check():
                raise RuntimeError("previous release also failed recovery health check")
        else:
            current.unlink(missing_ok=True)
        raise
    if previous:
        link_release(state / "previous", previous)
    print(f"Activated Credits {release.name}", flush=True)


def build(state, repository, revision):
    release = state / "releases" / revision
    if (release / "credits").is_file():
        return release
    release.mkdir(parents=True, exist_ok=True)
    # Rust targets and temporary files stay on the home filesystem, not /tmp tmpfs.
    with tempfile.TemporaryDirectory(prefix="build-", dir=state) as directory:
        source = Path(directory) / "source"
        source.mkdir()
        archive = Path(directory) / "source.tar"
        run("git", "--git-dir", str(repository), "archive", "--format=tar",
            f"--output={archive}", revision, timeout=120)
        with tarfile.open(archive) as contents:
            contents.extractall(source, filter="data")
        temporary = Path(directory) / "tmp"
        temporary.mkdir()
        env = dict(os.environ, CARGO_TARGET_DIR=str(state / "target"),
                   TMPDIR=str(temporary), MISE_YES="1")
        # Remote main is the explicitly authorized source of executable app code.
        run("mise", "trust", str(source / "mise.toml"), env=env, timeout=60)
        try:
            run("mise", "-C", str(source), "exec", "--", "cargo", "test", "--locked",
                env=env, timeout=1200)
            run("mise", "-C", str(source), "exec", "--", "cargo", "build", "--locked", "--release",
                env=env, timeout=1200)
            shutil.copy2(state / "target/release/credits", release / "credits.new")
            (release / "credits.new").replace(release / "credits")
        finally:
            run("mise", "trust", "--untrust", str(source / "mise.toml"), env=env, timeout=60)
    return release


def update(state, repository_url, retry=False):
    repository = state / "repository.git"
    if not repository.exists():
        run("git", "init", "--bare", str(repository), timeout=60)
        git(repository, "remote", "add", "origin", repository_url)
    if git(repository, "remote", "get-url", "origin") != repository_url:
        raise RuntimeError("private deployment repository has an unexpected origin")
    git(repository, "fetch", "--no-tags", "origin", "+refs/heads/main:refs/heads/main")
    revision = git(repository, "rev-parse", "refs/heads/main")
    current = state / "current"
    if current.is_symlink():
        old = current.resolve().name
        if old == revision:
            print(f"Credits is current at {revision}", flush=True)
            return
        # Never silently deploy rewritten/diverged history over a running release.
        git(repository, "merge-base", "--is-ancestor", old, revision)
    rejected = state / "rejected-revision"
    if not retry and rejected.exists() and rejected.read_text().strip() == revision:
        raise RuntimeError(f"revision {revision} previously failed; use credits-update --retry after fixing the cause")
    try:
        release = build(state, repository, revision)
        promote(state, release)
    except Exception:
        rejected.write_text(revision + "\n")
        raise
    rejected.unlink(missing_ok=True)


def main():
    if sys.argv[1:] not in ([], ["--retry"]):
        raise RuntimeError("usage: credits-update [--retry]")
    os.umask(0o077)
    state = Path(os.environ["CREDITS_STATE"])
    state.mkdir(parents=True, exist_ok=True)
    with (state / "update.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Credits update already running", flush=True)
            return
        update(state, os.environ["CREDITS_REPOSITORY"], retry="--retry" in sys.argv)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError, sqlite3.Error) as error:
        print(f"credits-update: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
