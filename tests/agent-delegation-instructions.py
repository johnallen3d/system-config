#!/usr/bin/env python3
"""Check delegation policy wiring and installed Pi context without model calls.

These checks prove instruction delivery, not model compliance or tool enforcement.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "modules/home-manager/agent-projects/delegation-instructions.md"
TARGETS = {
    "personal": (".config/pi/AGENTS.md", ".config/claude-personal/CLAUDE.md"),
    "work": (".config/pi-work/AGENTS.md", ".config/claude-gmatter/CLAUDE.md"),
}


def check_contexts(contexts, linux):
    policy = POLICY.read_text()
    work = (ROOT / "modules/home-manager/agent-projects/work-instructions.md").read_text()
    for profile, paths in TARGETS.items():
        pi, claude = (contexts[path] for path in paths)
        assert pi == claude, f"{profile}: Pi and Claude instructions differ"
        assert pi.count(policy) == 1, f"{profile}: shared delegation policy missing/duplicated"
        assert ("## Arch/Omarchy" in pi) == linux, profile
        assert ("## Git worktrees are required" in pi) == (profile == "work"), profile
        if profile == "work":
            assert pi.startswith(work), "Existing work instructions must remain intact"
    print(f"PASS {'Linux' if linux else 'Mac'}: all four global instruction files, profile isolation")


def check_evaluated():
    # path: includes new files without requiring a commit or index changes.
    expression = f"""
    let
      flake = builtins.getFlake {json.dumps('path:' + str(ROOT))};
      targets = builtins.fromJSON {json.dumps(json.dumps([p for pair in TARGETS.values() for p in pair]))};
      extract = config: builtins.listToAttrs (map (name: {{
        inherit name; value = config.home.file.${{name}}.text;
      }}) targets);
    in {{
      mac = extract flake.darwinConfigurations.m4-mbp.config.home-manager.users.\"john.allen\";
      linux = extract flake.homeConfigurations.\"johna@omarchy\".config;
    }}
    """
    result = subprocess.run(
        ["nix", "eval", "--impure", "--json", "--expr", expression],
        check=True, capture_output=True, text=True, timeout=180,
    )
    configs = json.loads(result.stdout)
    check_contexts(configs["mac"], False)
    check_contexts(configs["linux"], True)


def check_installed(loader):
    assert loader and loader.is_file(), "Provide --pi-loader for the installed Pi runtime"
    home = Path.home()
    contexts = {}
    for pair in TARGETS.values():
        for target in pair:
            path = home / target
            assert path.is_symlink(), f"Expected Home Manager ownership: {path}"
            contexts[target] = path.read_text()
    check_contexts(contexts, os.uname().sysname == "Linux")
    with tempfile.TemporaryDirectory(prefix="delegation-context-") as tmp:
        parent = Path(tmp)
        cwd = parent / "unrelated-project"
        cwd.mkdir()
        ancestor = parent / "AGENTS.md"
        ancestor.write_text("Ancestor context fixture\n")
        script = """
        const { loadProjectContextFiles } = await import(process.argv[1]);
        console.log(JSON.stringify(loadProjectContextFiles({
          cwd: process.argv[2], agentDir: process.argv[3]
        })));
        """
        for profile, (pi, claude) in TARGETS.items():
            env = dict(os.environ,
                       PI_CODING_AGENT_DIR=str((home / pi).parent),
                       CLAUDE_CONFIG_DIR=str((home / claude).parent))
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script, loader.as_uri(),
                 str(cwd), env["PI_CODING_AGENT_DIR"]],
                env=env, check=True, capture_output=True, text=True, timeout=30,
            )
            loaded = {Path(item["path"]).resolve(): item["content"]
                      for item in json.loads(result.stdout)}
            assert loaded[(home / pi).resolve()] == contexts[pi], profile
            assert loaded[ancestor.resolve()] == ancestor.read_text(), profile
            print(f"PASS installed Pi {profile}: native loader includes global policy outside Amfaro")
    print("Instruction delivery verified; no inference, delegation guarantee, or tool restriction claimed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--pi-loader", type=Path)
    args = parser.parse_args()
    policy = POLICY.read_text()
    for fragment in (
        "first substantive action", "only minimal launch discovery",
        "Do not read task files or skills", "act on Fizzy cards, edit, or test",
        "short brief", "authorization boundaries", "inherited working directory",
        "PI_CODING_AGENT_DIR", "CLAUDE_CONFIG_DIR", "read applicable instructions and skills itself",
        "authorized implementation, issue tracking", "concise outcome, card link",
        "blockers", "decisions", "transcripts, raw logs, or file dumps",
        "unavailable or fails", "report the blocker and stop", "Do not\n  execute the task in the parent",
        "John's explicit permission", "instruction-level policy, not a hard guarantee",
    ):
        assert fragment in policy, fragment
    module = (ROOT / "modules/home-manager/agent-projects.nix").read_text()
    assert "builtins.readFile ./agent-projects/delegation-instructions.md" in module
    for profile, paths in TARGETS.items():
        for target in paths:
            assert f'"{target}".text = {profile}Instructions;' in module, target
    assert '.config/claude-personal/CLAUDE.md' not in (
        ROOT / "modules/home-manager/coding-agents.nix").read_text()
    print("PASS shared policy boundaries and single ownership of all four global instruction files")
    if args.evaluate:
        check_evaluated()
    if args.installed:
        check_installed(args.pi_loader.resolve() if args.pi_loader else None)


if __name__ == "__main__":
    main()
