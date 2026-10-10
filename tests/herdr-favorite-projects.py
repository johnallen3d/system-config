#!/usr/bin/env python3
"""Test favorite provisioning in disposable homes, with no network/model calls."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modules/home-manager/scripts/ensure-herdr-projects.py"
FAVORITES = ROOT / "modules/home-manager/dotfiles/config/herdr/plugins/config/herdr.project-picker/projects.toml"


def git(path, *args, input=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
               GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid")
    return subprocess.run(["git", "-C", str(path), *args], input=input, env=env,
                          check=True, capture_output=True, text=True).stdout.strip()


def snapshot(path):
    return (git(path, "rev-parse", "HEAD"), git(path, "symbolic-ref", "HEAD"),
            git(path, "status", "--porcelain"), (path / ".git/config").read_bytes())


def main():
    catalog = tomllib.loads(FAVORITES.read_text())
    projects = [p for session in catalog["sessions"].values() for p in session["projects"]]
    assert projects, "The favorite catalog must not be empty"
    assert all(p["path"].startswith("~/dev/src/") and p["clone_url"] for p in projects)
    work_projects = catalog["sessions"]["work"]["projects"]
    personal_paths = {p["path"] for p in catalog["sessions"]["personal"]["projects"]}
    for name in ("duckdb-embedded", "llm-usage"):
        path = f"~/dev/src/amfaro/{name}"
        entries = [p for p in work_projects if p["path"] == path]
        assert entries == [{"path": path, "clone_url": f"https://github.com/amfaro/{name}.git"}]
        assert path not in personal_paths, f"Work favorite leaked into personal session: {path}"

    with tempfile.TemporaryDirectory(prefix="herdr-favorites-") as tmp:
        root = Path(tmp)
        source = root / "source"
        source.mkdir()
        git(source, "init", "-b", "main")
        tree = git(source, "mktree", input="")
        commit = git(source, "commit-tree", tree, input="Fixture\n")
        git(source, "update-ref", "refs/heads/main", commit)
        home = root / "home"
        home.mkdir()
        manifest = root / "projects.json"

        def run(entries, dry=False, success=True):
            manifest.write_text(json.dumps(entries))
            result = subprocess.run(["python3", str(SCRIPT), str(manifest), str(home),
                                     *(["--dry-run"] if dry else [])], capture_output=True, text=True)
            assert (result.returncode == 0) == success, (result.stdout, result.stderr)
            return result

        project = {"path": "~/dev/src/repo with spaces", "clone_url": str(source)}
        run([project], dry=True)
        assert not (home / "dev").exists()
        run([project, project])
        checkout = home / "dev/src/repo with spaces"
        assert git(checkout, "rev-parse", "HEAD") == commit
        git(checkout, "switch", "-c", "unfinished")
        (checkout / "uncommitted.txt").write_text("Do not touch\n")
        before = snapshot(checkout)
        run([dict(project, clone_url="/unavailable-source")])
        run([project], dry=True)
        assert snapshot(checkout) == before

        worktree = home / "dev/src/worktree"
        git(checkout, "worktree", "add", "-b", "feature", str(worktree))
        (worktree / "dirty.txt").write_text("Unfinished\n")
        worktree_before = git(worktree, "status", "--porcelain")
        run([{"path": "~/dev/src/worktree", "clone_url": "/unavailable-source"}])
        assert git(worktree, "status", "--porcelain") == worktree_before

        collision = home / "dev/src/collision"
        collision.mkdir()
        (collision / "keep.txt").write_text("keep")
        run([{"path": "~/dev/src/collision", "clone_url": str(source)}], success=False)
        assert (collision / "keep.txt").read_text() == "keep"
        # A directory inside another repository is not a repository root.
        child = checkout / "child"
        child.mkdir()
        run([{"path": "~/dev/src/repo with spaces/child", "clone_url": str(source)}], success=False)
        broken = home / "dev/src/broken-link"
        broken.symlink_to(root / "missing")
        run([{"path": "~/dev/src/broken-link", "clone_url": str(source)}], success=False)
        assert broken.is_symlink()

        missing = {"path": "~/dev/src/missing", "clone_url": str(root / "absent")}
        later = {"path": "~/dev/src/later", "clone_url": str(source)}
        run([missing, later], success=False)
        assert not (home / "dev/src/missing").exists()
        assert not list((home / "dev/src").glob(".missing-clone-*"))
        assert git(home / "dev/src/later", "rev-parse", "HEAD") == commit
        run([{"path": "~/../escape", "clone_url": str(source)}], success=False)

        seed = home / ".local/share/herdr/project-seeds/test.bundle"
        seed.parent.mkdir(parents=True)
        git(source, "bundle", "create", str(seed), "--all")
        bundle_project = {"path": "~/dev/src/seeded", "clone_url": "~/.local/share/herdr/project-seeds/test.bundle"}
        run([bundle_project])
        assert git(home / "dev/src/seeded", "rev-parse", "HEAD") == commit
        assert git(home / "dev/src/seeded", "remote") == ""
        seed.unlink()
        run([bundle_project])
        # Removing a favorite never removes its existing checkout.
        run([])
        assert checkout.is_dir()

    print("Herdr favorite project tests passed (clones, dry run, idempotence, worktrees, collisions, failures, bundles).")


if __name__ == "__main__":
    main()
