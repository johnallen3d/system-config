#!/usr/bin/env python3
"""Check that managed agent environments do not set the 1M context opt-out.

--installed probes fresh personal/work environments without inference. It clears
stale inherited session variables in child processes only, never active agents.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

FLAG = "CLAUDE_CODE_DISABLE_1M_CONTEXT"
ROOT = Path(__file__).resolve().parents[1]


def source_checks():
    for relative in (
        "modules/home-manager/default.nix",
        "modules/home-manager/packages/coding-agents.nix",
        "modules/home-manager/agent-projects/amfaro-mise.toml",
    ):
        assert FLAG not in (ROOT / relative).read_text(), relative
    print("PASS source: no managed context opt-out assignment")


def installed_checks():
    home = Path.home()
    roots = (
        Path("/etc/profiles/per-user") / home.name,
        home / ".nix-profile",
    )
    session_files = [
        root / "etc/profile.d" / name
        for root in roots
        for name in ("hm-session-vars.sh", "hm-session-vars.fish")
        if (root / "etc/profile.d" / name).is_file()
    ]
    assert session_files, "No installed Home Manager session variables found"
    for path in session_files:
        assert FLAG not in path.read_text(), str(path)
    print("PASS installed: Home Manager session variables omit context opt-out")

    env = dict(os.environ)
    for key in (FLAG, "__HM_SESS_VARS_SOURCED", "__HM_SESS_VARS_DONE"):
        env.pop(key, None)
    # Select personal in the child without disturbing the caller's Pi profile.
    env.update(
        PI_CODING_AGENT_DIR=str(home / ".config/pi"),
        CLAUDE_CONFIG_DIR=str(home / ".config/claude-personal"),
    )
    fish = shutil.which("fish")
    assert fish, "Fish not installed"
    probe = (
        "import json,os; print(json.dumps({k:os.environ.get(k) for k in "
        f"{[FLAG, 'PI_CODING_AGENT_DIR', 'CLAUDE_CONFIG_DIR']!r}}}))"
    )
    with tempfile.TemporaryDirectory(prefix="context-environment-") as directory:
        script = Path(directory) / "probe.py"
        script.write_text(probe + "\n")
        probe_command = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
        commands = [("environment", probe_command)]
        launcher = home / ".local/bin/claude"
        if sys.platform.startswith("linux"):
            lines = launcher.read_text().splitlines()
            assert FLAG not in "\n".join(lines), str(launcher)
            exec_lines = [i for i, line in enumerate(lines) if line.startswith("exec ")]
            assert len(exec_lines) == 1, "Unexpected Claude wrapper structure"
            lines[exec_lines[0]] = f"exec {probe_command}"
            wrapper = Path(directory) / "claude-probe"
            wrapper.write_text("\n".join(lines) + "\n")
            commands.append(("Claude launcher", f"bash {shlex.quote(str(wrapper))}"))
        for profile, pi_name, claude_name in (
            ("personal", "pi", "claude-personal"),
            ("work", "pi-work", "claude-gmatter"),
        ):
            for label, command in commands:
                if profile == "work":
                    command = f"mise -C {shlex.quote(str(home / 'dev/src/amfaro'))} exec -- {command}"
                result = subprocess.run(
                    [fish, "-lc", command], cwd=home, env=env, check=True,
                    capture_output=True, text=True, timeout=60,
                )
                actual = json.loads(result.stdout)
                assert actual == {
                    FLAG: None,
                    "PI_CODING_AGENT_DIR": str(home / ".config" / pi_name),
                    "CLAUDE_CONFIG_DIR": str(home / ".config" / claude_name),
                }, (profile, label, actual)
                print(f"PASS {profile} {label}: flag absent; both profile directories preserved")
    if FLAG in os.environ:
        print("NOTE caller retains the old flag; clear it in the launching shell before starting new agents")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    source_checks()
    if args.installed:
        installed_checks()
