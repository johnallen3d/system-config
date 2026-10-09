#!/usr/bin/env python3
"""Check shared work policy and optional installed context without model calls."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "modules/home-manager/agent-projects/work-instructions.md"


def git(cwd, *args):
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def is_linked(cwd):
    paths = git(cwd, "rev-parse", "--path-format=absolute", "--git-dir",
                "--git-common-dir").splitlines()
    return Path(paths[0]).resolve() != Path(paths[1]).resolve()


def check_git_rule():
    with tempfile.TemporaryDirectory() as tmp:
        parent = Path(tmp)
        primary = parent / "primary"
        git(parent, "init", "--quiet", str(primary))
        tree = git(primary, "hash-object", "-t", "tree", "-w", "/dev/null")
        commit = git(primary, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                     "-c", "commit.gpgsign=false", "commit-tree", tree,
                     "-m", "test: create disposable worktree fixture")
        git(primary, "symbolic-ref", "HEAD", "refs/heads/feature/test-primary")
        git(primary, "update-ref", "HEAD", commit)
        assert not is_linked(primary), "Feature branches in primary are not linked worktrees"
        linked = parent / "linked"
        git(primary, "worktree", "add", "--quiet", "-b", "feature/test-linked", str(linked))
        assert is_linked(linked)
        alias = parent / "linked-alias"
        alias.symlink_to(linked, target_is_directory=True)
        assert is_linked(alias), "Canonicalize symlinks when checking worktrees"
    print("PASS worktree check: primary feature branch rejected; linked and symlink accepted")


def check_installed(loader):
    home = Path.home()
    pi = home / ".config/pi-work/AGENTS.md"
    claude = home / ".config/claude-gmatter/CLAUDE.md"
    for file in (pi, claude):
        assert file.is_symlink(), f"Expected Home Manager ownership: {file}"
        assert file.read_text().startswith(SOURCE.read_text()), file
    assert pi.read_text() == claude.read_text(), "Agents must share the same work policy"
    linux = os.uname().sysname == "Linux"
    assert ("## Arch/Omarchy" in pi.read_text()) == linux
    for file in (home / ".config/pi/AGENTS.md", home / ".config/claude-personal/CLAUDE.md"):
        assert not file.exists() or "Git worktrees are required" not in file.read_text(), file
    assert os.environ.get("PI_CODING_AGENT_DIR") == str(pi.parent)
    assert os.environ.get("CLAUDE_CONFIG_DIR") == str(claude.parent)
    print("PASS installed policy: both agents identical, host guidance and profile isolation")
    assert loader and loader.is_file(), "Provide --pi-loader for the installed Pi runtime"
    node = shutil.which("node")
    assert node, "Run installed checks via mise exec for Node"
    with tempfile.TemporaryDirectory() as tmp:
        parent = Path(tmp)
        nested = parent / "child"
        nested.mkdir()
        ancestor = parent / "AGENTS.md"
        ancestor.write_text("Ancestor context fixture\n")
        script = """
const {loadProjectContextFiles} = await import(process.argv[1]);
const contexts = loadProjectContextFiles({cwd:process.argv[2], agentDir:process.argv[3]});
console.log(JSON.stringify(contexts));
"""
        result = subprocess.run(
            [node, "--input-type=module", "-e", script, loader.as_uri(), str(nested), str(pi.parent)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        contexts = {Path(item["path"]).resolve(): item["content"]
                    for item in json.loads(result.stdout)}
        assert contexts[pi.resolve()] == pi.read_text()
        assert contexts[ancestor.resolve()] == ancestor.read_text()
    print("PASS installed Pi loader reads work-global and parent AGENTS.md outside Amfaro")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--pi-loader", type=Path)
    args = parser.parse_args()
    source = SOURCE.read_text()
    for fragment in ("linked Git worktree", "task-specific branch", "primary checkout",
                     "git worktree list --porcelain", "--git-dir --git-common-dir",
                     "PI_CODING_AGENT_DIR", "CLAUDE_CONFIG_DIR", "uncommitted changes",
                     "stop and report", "explicitly authorizes"):
        assert fragment in source, fragment
    module = (ROOT / "modules/home-manager/agent-projects.nix").read_text()
    assert "builtins.readFile ./agent-projects/work-instructions.md" in module
    for target in (".config/pi-work/AGENTS.md", ".config/claude-gmatter/CLAUDE.md"):
        assert f'"{target}".text = workInstructions;' in module
    assert "pkgs.stdenv.hostPlatform.isLinux" in module
    assert '.config/claude-gmatter/CLAUDE.md' not in (
        ROOT / "modules/home-manager/coding-agents.nix").read_text()
    print("PASS single shared policy source, platform guidance, no duplicate declarations")
    check_git_rule()
    if args.installed:
        check_installed(args.pi_loader)


if __name__ == "__main__":
    main()
