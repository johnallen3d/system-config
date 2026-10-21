#!/usr/bin/env python3
"""Host-local deployment lock and Git-tree provenance. Never commit or integrate tasks."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import signal
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


CANCELLED = None
# Legacy coordinator worktrees only; new sources never register a worktree.
SOURCE_SLUG = re.compile(r"(?:deployment|update-system)-([0-9a-f]{12})")


def check_cancelled():
    if CANCELLED is not None:
        raise RuntimeError(f"Deployment interrupted by signal {CANCELLED}; no further activation will start")


def run(*args, cwd=None, env=None):
    return subprocess.check_output(args, cwd=cwd, env=env, text=True).strip()


def git(repo, *args, **kwargs):
    return run("git", "-C", str(repo), *args, **kwargs)


def source_tree(repo):
    if git(repo, "ls-files", "--unmerged"):
        raise RuntimeError(f"Unresolved Git conflicts: {repo}")
    with tempfile.TemporaryDirectory(prefix="deployment-index-") as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        git(repo, "read-tree", "HEAD", env=env)
        git(repo, "add", "-A", "--", ".", env=env)
        return git(repo, "write-tree", env=env)


def state_dir():
    # Deliberately independent of Pi/Claude profiles: hosts share deployment state,
    # never credentials, profile settings, or sessions.
    return Path.home() / ".local/state/system-config/deployment"


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        json.dump(data, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


@contextmanager
def lock(directory, owner, timeout=600):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "lock").open("a+") as handle:
        deadline = time.monotonic() + timeout
        announced = False
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                handle.seek(0)
                busy = handle.read().strip()
                if not announced:
                    print(f"[deployment] Waiting for active deployment: {busy}", flush=True)
                    announced = True
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Deployment busy: {busy}; retry after its owner finishes (do not bypass the lock)")
                time.sleep(.2)
        handle.seek(0)
        handle.truncate()
        json.dump({"pid": os.getpid(), "owner": owner, "started": time.time()}, handle)
        handle.flush()
        def interrupted(signum, _frame):
            global CANCELLED
            CANCELLED = signum
            print("[deployment] Interrupted; retaining activation lock while current child exits", file=sys.stderr, flush=True)

        handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            yield handle
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            fcntl.flock(handle, fcntl.LOCK_UN)


def current_generation():
    path = Path("/run/current-system") if sys.platform == "darwin" else Path.home() / ".local/state/nix/profiles/home-manager"
    if not path.exists():
        raise RuntimeError(f"Active generation is missing: {path}")
    return str(path.resolve())


def evaluated_generation(repo):
    if sys.platform == "darwin":
        attribute = f'darwinConfigurations."{run("hostname", "-s")}".system.outPath'
    else:
        attribute = 'homeConfigurations."johna@omarchy".activationPackage.outPath'
    return run("nix", "--extra-experimental-features", "nix-command flakes", "eval", "--raw", "--impure",
               "--no-update-lock-file", "--no-write-lock-file", f"path:{repo}#{attribute}")


def primary(repo):
    return Path(git(repo, "worktree", "list", "--porcelain").splitlines()[0].removeprefix("worktree ")).resolve()


def layer(repo, owner=None):
    branch = git(repo, "symbolic-ref", "--short", "HEAD")
    main = git(repo, "rev-parse", "refs/heads/main")
    bases = git(repo, "merge-base", "--all", main, "HEAD").splitlines()
    if len(bases) != 1:
        raise RuntimeError("Task must have a unique merge base with local main")
    return {"owner": owner or branch, "origin": str(repo.resolve()), "head": git(repo, "rev-parse", "HEAD"),
            "base": bases[0], "tree": source_tree(repo)}


def entries(repo, tree):
    output = subprocess.check_output(["git", "-C", str(repo), "ls-tree", "-rz", tree])
    result = {}
    for item in output.split(b"\0"):
        if item:
            metadata, name = item.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            if kind != "blob":
                raise RuntimeError("Submodules are not supported in deployment sources")
            result[os.fsdecode(name)] = (mode, oid)
    return result


def compose(repo, main, layers):
    """File-level ownership is intentional: no speculative textual auto-merges."""
    baseline = entries(repo, main)
    changes = {}
    for item in layers:
        before, after = entries(repo, item["base"]), entries(repo, item["tree"])
        for path in sorted(before.keys() | after.keys()):
            old, new, integrated = before.get(path), after.get(path), baseline.get(path)
            if old == new or integrated == new:
                continue
            if integrated != old:
                raise RuntimeError(f"Overlapping change: {path!r}; owner {item['owner']} versus integrated main. No activation started.")
            if path in changes and changes[path][0] != new:
                raise RuntimeError(f"Overlapping change: {path!r}; owners {changes[path][1]} and {item['owner']}. No activation started.")
            changes[path] = (new, item["owner"])
    with tempfile.TemporaryDirectory(prefix="deployment-compose-") as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"))
        git(repo, "read-tree", main, env=env)
        for path, (entry, _) in changes.items():
            if entry is None:
                git(repo, "update-index", "--force-remove", "--", path, env=env)
            else:
                mode, oid = entry
                git(repo, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}", env=env)
        return git(repo, "write-tree", env=env)


def normalize(repo, main, layers):
    # Retire integrated paths, including part of a multi-file layer, so a later
    # main edit is not incorrectly attributed to an already-integrated task.
    baseline = git(repo, "rev-parse", f"{main}^{{tree}}")
    result = []
    for item in layers:
        tree = compose(repo, main, [item])
        if tree != baseline:
            result.append(dict(item, base=main, tree=tree))
    return result


def retire_formatted_integrations(repo, main, layers, generation):
    """Retire a fully integrated layer whose only differences are Nix syntax layout.

    Never merge files or rewrite active receipts. Parsed expressions must match
    for every nonidentical path, and the preserved source must evaluate to the
    exact installed generation before the ordinary deployment can proceed.
    """
    baseline = entries(repo, main)
    parsed = {}

    def expression(entry):
        if entry not in parsed:
            blob = subprocess.check_output(["git", "-C", str(repo), "cat-file", "blob", entry[1]])
            parsed[entry] = subprocess.check_output(["nix-instantiate", "--parse", "-"], input=blob, cwd=repo)
        return parsed[entry]

    remaining, retired = [], []
    for item in layers:
        before, after = entries(repo, item["base"]), entries(repo, item["tree"])
        formatted = False
        for path in before.keys() | after.keys():
            old, new, integrated = before.get(path), after.get(path), baseline.get(path)
            if old == new or integrated == new:
                continue
            if (integrated == old or not path.endswith(".nix") or new is None or integrated is None
                    or new[0] not in ("100644", "100755") or new[0] != integrated[0]
                    or expression(new) != expression(integrated)):
                remaining.append(item)
                break
            formatted = True
        else:
            (retired if formatted else remaining).append(item)
    if not retired:
        return layers
    preserved = materialize(repo, main, compose(repo, main, remaining))
    if evaluated_generation(preserved) != generation:
        raise RuntimeError("Formatted integration does not reproduce the exact installed generation; no activation started")
    for item in retired:
        print(f"[deployment] Verified formatted integration of {item['owner']} against the exact installed generation", file=sys.stderr, flush=True)
    return remaining


@contextmanager
def temporary_sources():
    # The lock owner outlives all build/activation children. Its finally block
    # removes sources on success, failure and handled interruption, not at plan exit.
    previous = os.environ.get("SYSTEM_CONFIG_TEMP_ROOT")
    with tempfile.TemporaryDirectory(prefix="system-config-deploy-") as directory:
        # macOS TMPDIR usually starts with the /var symlink; Nix path flakes
        # require canonical parent components, so use /private/var instead.
        os.environ["SYSTEM_CONFIG_TEMP_ROOT"] = str(Path(directory).resolve())
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("SYSTEM_CONFIG_TEMP_ROOT", None)
            else:
                os.environ["SYSTEM_CONFIG_TEMP_ROOT"] = previous


def snapshot_tree(repo, source):
    """Hash a plain source directory, including ignored files, without its own Git repo."""
    with tempfile.TemporaryDirectory(prefix="deployment-index-") as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"),
                   GIT_DIR=git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"),
                   GIT_WORK_TREE=str(source))
        git(source, "read-tree", "--empty", env=env)
        git(source, "add", "--force", "-A", "--", ".", env=env)
        return git(source, "write-tree", env=env)


def materialize(repo, main, tree):
    directory = os.environ.get("SYSTEM_CONFIG_TEMP_ROOT")
    if not directory or not Path(directory).is_dir():
        raise RuntimeError("Deployment source requires the lock owner's temporary directory")
    source = Path(directory) / ("source-" + hashlib.sha256(f"{main}:{tree}".encode()).hexdigest()[:12])
    if not source.exists():
        source.mkdir()
        with tempfile.TemporaryDirectory(prefix="deployment-index-") as index:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(index) / "index"))
            git(repo, "read-tree", tree, env=env)
            # Unlike git archive, checkout-index retains export-ignore files and
            # does not perform export-subst: this is the complete recorded tree.
            git(repo, "checkout-index", "--all", "--prefix=" + str(source) + "/", env=env)
    if snapshot_tree(repo, source) != tree:
        raise RuntimeError(f"Deployment source changed; refusing to overwrite {source}")
    return source


def durable(record):
    # Temporary paths are build handles, never durable provenance dependencies.
    return {key: value for key, value in record.items() if key not in ("source", "previous_source")}


def validate(repo, record, require_source=False):
    if Path(record["repository"]).resolve() != primary(repo):
        raise RuntimeError("Deployment provenance belongs to another repository")
    if record.get("version", 1) == 1:
        # Upgrade only through a verified normal activation. Never silently accept
        # a missing/edited legacy source or rewrite its receipt to make it pass.
        source = Path(record["source"])
        slug = "deployment-" + hashlib.sha256(f"{record['main']}:{record['tree']}".encode()).hexdigest()[:12]
        if (source.resolve() != primary(repo) / ".worktrees" / slug
                or git(source, "rev-parse", "HEAD") != record["main"]
                or git(source, "symbolic-ref", "--short", "HEAD") != "feature/" + slug):
            raise RuntimeError(f"Recorded deployment worktree ownership/base changed: {source}")
        if source_tree(source) != record["tree"]:
            raise RuntimeError(f"Recorded deployment source was edited: {source}; recover provenance before activation")
    elif record["version"] == 2:
        for tree in {record["tree"], *(item["tree"] for item in record["layers"])}:
            if git(repo, "rev-parse", f"refs/system-config/trees/{tree}") != tree:
                raise RuntimeError(f"Deployment tree is not pinned: {tree}")
        if require_source:
            source = Path(record["source"])
            directory = os.environ.get("SYSTEM_CONFIG_TEMP_ROOT")
            if (not directory or source.parent.resolve() != Path(directory).resolve()
                    or not source.is_dir() or source.is_symlink()
                    or snapshot_tree(repo, source) != record["tree"]):
                raise RuntimeError(f"Temporary deployment source changed or is missing: {source}")
    else:
        raise RuntimeError("Unsupported deployment receipt version")
    # Missing/pruned objects or changed layer data must fail before any activation.
    if compose(repo, record["main"], record["layers"]) != record["tree"]:
        raise RuntimeError("Deployment provenance cannot reproduce its recorded source")


def active(repo, directory):
    current = current_generation()
    # Activation might succeed before its caller is interrupted. Recover only an
    # exact, source-verified pending generation, never an arbitrary rollback.
    pending = directory / "pending.json"
    if pending.exists():
        candidate = json.loads(pending.read_text())
        if candidate["generation"] == current:
            validate(repo, candidate)
            atomic_json(directory / "active.json", durable(candidate) if candidate.get("version") == 2 else candidate)
            pending.unlink()
    path = directory / "active.json"
    if not path.exists():
        raise RuntimeError("Active deployment provenance is unknown. Evaluate registered candidate sources against the installed generation and adopt only an exact match with verified task ownership; do not activate main or collect every dirty worktree.")
    record = json.loads(path.read_text())
    if record["generation"] != current:
        raise RuntimeError(f"Unrecorded activation/rollback: active {current}, recorded {record['generation']}. Recover exact provenance before retrying.")
    validate(repo, record)
    return record


def pin(repo, record):
    # Retain trees and their baseline history through GC without creating commits
    # or moving task/main branches. No checkout needs to survive activation.
    for commit in {record["main"], *(item["base"] for item in record["layers"])}:
        git(repo, "update-ref", f"refs/system-config/commits/{commit}", commit)
    for item in record["layers"]:
        git(repo, "update-ref", f"refs/system-config/trees/{item['tree']}", item["tree"])
    git(repo, "update-ref", f"refs/system-config/trees/{record['tree']}", record["tree"])


def plan(repo, directory, incoming=None):
    check_cancelled()
    previous = active(repo, directory)
    incoming = incoming or layer(repo)
    main = git(repo, "rev-parse", "refs/heads/main")
    if subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", previous["main"], main]).returncode:
        raise RuntimeError("Local main rewound/diverged since the active deployment")
    # Reconcile only already-active, fully integrated layers, before considering
    # this task's incoming changes. Active/pending receipts remain untouched.
    preserved = retire_formatted_integrations(repo, main, previous["layers"], previous["generation"])
    layers = [item for item in preserved if item["owner"] != incoming["owner"]] + [incoming]
    tree = compose(repo, main, layers)
    layers = normalize(repo, main, layers)
    source = materialize(repo, main, tree)
    record = {"version": 2, "repository": str(primary(repo)), "main": main, "tree": tree,
              "source": str(source), "layers": layers, "generation": evaluated_generation(source),
              "previous_generation": previous["generation"], "previous_main": previous["main"],
              "previous_tree": previous["tree"]}
    check_cancelled()
    pin(repo, record)
    atomic_json(directory / "pending.json", record)
    print(f"[deployment] Source {source}; owners: {', '.join(item['owner'] for item in layers)}", file=sys.stderr, flush=True)
    return record


def preactivate(repo, directory):
    check_cancelled()
    record = json.loads((directory / "pending.json").read_text())
    if current_generation() != record["previous_generation"]:
        raise RuntimeError("Active generation changed after deployment planning; no activation started")
    validate(repo, record, require_source=True)


def finish(repo, directory):
    record = json.loads((directory / "pending.json").read_text())
    if current_generation() != record["generation"]:
        raise RuntimeError("Installed generation does not match planned deployment")
    validate(repo, record, require_source=True)
    atomic_json(directory / "active.json", durable(record))
    (directory / "pending.json").unlink()
    # The activation is recorded; cleanup failure or interruption must not report it as failed.
    try:
        prune(repo, directory, keep=(repo,))
    except (Exception, KeyboardInterrupt) as error:
        print(f"[deployment] Activation recorded; source worktree pruning skipped: {error}", file=sys.stderr, flush=True)


def worktrees(root):
    result = []
    for block in git(root, "worktree", "list", "--porcelain").split("\n\n"):
        fields = dict((line.split(" ", 1) + [""])[:2] for line in block.splitlines() if line)
        if "worktree" in fields:
            result.append(fields)
    return result


def prune(repo, directory, keep=()):
    """Remove verified legacy coordinator worktrees. Caller holds the host lock.

    Only a coordinator-named worktree on its own branch whose content still equals
    the main commit and tree its name was derived from is removed, after pinning
    that tree. Sources still required by legacy receipts, task worktrees, edited
    snapshots, ignored files, and branches with commits outside main are kept.
    Snapshot-based receipts do not retain active/previous source directories.
    """
    check_cancelled()
    if not (directory / "active.json").exists():
        raise RuntimeError("Active deployment provenance is unknown; refusing to prune source worktrees")
    root = primary(repo)
    retained = {root, *(Path(path).resolve() for path in keep)}
    for name in ("active.json", "pending.json"):
        if (directory / name).exists():
            record = json.loads((directory / name).read_text())
            retained.update(Path(record[key]).resolve() for key in ("source", "previous_source") if key in record)
    main = git(root, "rev-parse", "refs/heads/main")
    removed, kept = [], []
    for fields in worktrees(root):
        path = Path(fields["worktree"]).resolve()
        match = SOURCE_SLUG.fullmatch(path.name)
        if not match or path.parent != root / ".worktrees" or path in retained:
            continue
        head, branch = fields.get("HEAD", ""), "feature/" + path.name
        try:
            if "locked" in fields or "prunable" in fields or fields.get("branch") != "refs/heads/" + branch:
                raise RuntimeError("not an unlocked coordinator worktree on its own branch")
            if subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", head, main]).returncode:
                raise RuntimeError("branch has commits outside main")
            tree = source_tree(path)
            if hashlib.sha256(f"{head}:{tree}".encode()).hexdigest()[:12] != match.group(1):
                raise RuntimeError("source differs from the tree its name records")
            # Python bytecode left by importing coordinator scripts is disposable.
            ignored = [name for name in git(path, "ls-files", "--others", "--ignored", "--exclude-standard").splitlines()
                       if not (name.endswith(".pyc") and "__pycache__" in Path(name).parts)]
            if ignored:
                raise RuntimeError("contains ignored files")
            git(root, "update-ref", f"refs/system-config/trees/{tree}", tree)
            git(root, "worktree", "remove", "--force", str(path))
            git(root, "update-ref", "-d", "refs/heads/" + branch, head)
            removed.append(path.name)
        except (RuntimeError, subprocess.CalledProcessError) as error:
            kept.append(f"{path.name} ({error})")
    if removed:
        print(f"[deployment] Pruned {len(removed)} superseded source worktree(s); trees remain pinned", file=sys.stderr, flush=True)
    for item in kept:
        print(f"[deployment] Kept source worktree {item}", file=sys.stderr, flush=True)
    return removed, kept


def adopt(repo, source, owner, directory):
    if (directory / "active.json").exists() or (directory / "pending.json").exists():
        raise RuntimeError("Provenance already exists; adoption cannot replace an existing record")
    incoming = layer(source, owner)
    main = git(repo, "rev-parse", "refs/heads/main")
    tree = compose(repo, main, [incoming])
    snapshot = materialize(repo, main, tree)
    generation = evaluated_generation(snapshot)
    if generation != current_generation():
        raise RuntimeError(f"Candidate does not reproduce installed generation: {generation}")
    record = {"version": 2, "repository": str(primary(repo)), "main": main, "tree": tree,
              "generation": generation, "layers": [incoming]}
    pin(repo, record)
    atomic_json(directory / "active.json", record)
    print(f"[deployment] Adopted exact installed generation from {source} (owner {owner})", flush=True)


def main():
    if len(sys.argv) < 3 or (sys.argv[1] == "apply" and sys.argv[2] in ("-h", "--help")):
        print("Usage: system-config-deploy TASK_PATH [--switch-only|--picker-only] [--local-only] [--harness-refresh|--harness-only]")
        return 0
    mode, repo = sys.argv[1], Path(sys.argv[2]).resolve()
    directory = state_dir()
    if mode == "apply":
        allowed = {"--switch-only", "--picker-only", "--local-only", "--harness-refresh", "--harness-only"}
        flags = sys.argv[3:]
        if any(flag not in allowed for flag in flags):
            raise RuntimeError("Unknown deployment flag")
        tool_root = Path(__file__).resolve().parents[2]
        env = {key: value for key, value in os.environ.items() if not key.startswith(("usage_", "SYSTEM_CONFIG_"))}
        env.update(SYSTEM_CONFIG_TASK_ROOT=str(repo), SYSTEM_CONFIG_TOOL_ROOT=str(tool_root))
        env.update({"usage_" + flag[2:].replace("-", "_"): "true" for flag in flags})
        if sys.platform == "darwin" or "--harness-only" in flags:
            command = ["bash", str(tool_root / ".mise/tasks/update-system")]
        else:
            if flags != ["--switch-only"]:
                raise RuntimeError("Linux activation requires --switch-only; no macOS tasks or implicit input updates")
            command = [sys.executable, str(tool_root / ".mise/scripts/update-system-omarchy"), "local", str(repo)]
        # The caller already selected mise context. Re-entering mise in this
        # checkout could undo the inherited work profile when invoked from
        # ~/dev/src/amfaro. Preserve that environment while selecting only cwd.
        return subprocess.run(command, cwd=repo, env=env).returncode
    elif mode == "run":
        with lock(directory, str(repo)) as handle, temporary_sources():
            env = dict(os.environ, SYSTEM_CONFIG_COORDINATED=str(repo))
            env.pop("SYSTEM_CONFIG_SOURCE", None)
            child = subprocess.Popen(sys.argv[3:], env=env, pass_fds=(handle.fileno(),))
            previous = {}
            def forward(signum, _frame):
                global CANCELLED
                CANCELLED = signum
                child.send_signal(signum)
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, forward)
            try:
                return child.wait()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    elif mode == "plan":
        record = plan(repo, directory)
        Path(sys.argv[3]).write_text(record["source"])
    elif mode == "guard":
        preactivate(repo, directory)
    elif mode == "finish":
        finish(repo, directory)
    elif mode == "adopt":
        with lock(directory, "adopt " + sys.argv[4]), temporary_sources():
            adopt(repo, Path(sys.argv[3]).resolve(), sys.argv[4], directory)
    elif mode == "prune":
        with lock(directory, "prune " + str(repo)):
            active(repo, directory)
            prune(repo, directory, keep=(repo,))
    elif mode == "status":
        lock_path = directory / "lock"
        busy = False
        if lock_path.exists():
            with lock_path.open("r+") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except BlockingIOError:
                    busy = True
        print(f"activation lock held: {busy}")
        for name in ("lock", "active.json", "pending.json"):
            path = directory / name
            print(f"{name}: {path.read_text() if path.exists() else 'missing'}")
        print(f"installed: {current_generation()}")
    else:
        raise RuntimeError(f"Unknown mode: {mode}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError, KeyError) as error:
        print(f"[deployment] {error}", file=sys.stderr, flush=True)
        sys.exit(1)
