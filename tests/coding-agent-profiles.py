#!/usr/bin/env python3
"""Check installed launchers without installing packages or invoking a model.

Run on Omarchy: python3 tests/coding-agent-profiles.py
Replaces only the final exec in a temporary script; tests the installed wiring.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    home = Path.home()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        probe = directory / "probe.py"
        probe.write_text(
            "import json, os, sys\n"
            "print(json.dumps({'pi': os.environ.get('PI_CODING_AGENT_DIR'), "
            "'claude': os.environ.get('CLAUDE_CONFIG_DIR'), 'args': sys.argv[1:]}))\n"
        )
        for agent in ("pi", "claude"):
            for profile, pi_dir, claude_dir in (
                ("personal", "pi", "claude-personal"),
                ("work", "pi-work", "claude-gmatter"),
            ):
                name = f"{agent}-{profile}"
                source = (home / ".local/bin" / name).read_text()
                lines = source.splitlines()
                exec_lines = [i for i, line in enumerate(lines) if line.startswith("exec ")]
                assert len(exec_lines) == 1, name
                lines[exec_lines[0]] = f'exec python3 "{probe}" "$@"'
                script = directory / name
                script.write_text("\n".join(lines) + "\n")
                env = dict(os.environ)
                env.update(PI_CODING_AGENT_DIR="/wrong/pi", CLAUDE_CONFIG_DIR="/wrong/claude")
                args = ["--test", "argument with spaces"]
                result = subprocess.run(
                    ["bash", str(script), *args], env=env, check=True,
                    capture_output=True, text=True,
                )
                actual = json.loads(result.stdout)
                assert actual == {
                    "pi": str(home / ".config" / pi_dir),
                    "claude": str(home / ".config" / claude_dir),
                    "args": args,
                }, (name, actual)
                print(f"PASS {name}: paired profile overrides inherited context; arguments intact")

        # Exercise the base Pi wrapper without executing its package installer.
        source = (home / ".local/bin/pi").read_text().splitlines()
        exec_lines = [i for i, line in enumerate(source) if line.startswith("exec ")]
        assert len(exec_lines) == 1
        source[exec_lines[0]] = 'printf "%s\\n" "$SHARP_IGNORE_GLOBAL_LIBVIPS"'
        script = directory / "base-pi"
        script.write_text("\n".join(source) + "\n")
        env = dict(os.environ, SHARP_IGNORE_GLOBAL_LIBVIPS="0")
        result = subprocess.run(["bash", str(script)], env=env, check=True,
                                capture_output=True, text=True)
        assert result.stdout.strip() == "1"
        print("PASS Pi installer ignores global libvips and uses bundled Sharp binaries")

        personal = home / ".config/pi"
        work = home / ".config/pi-work"
        for profile in (personal, work):
            mcp = (profile / "mcp-adapter.json").read_text()
            assert "/Users/" not in mcp and "security find-generic-password" not in mcp
            settings = json.loads((profile / "settings.json").read_text())
            assert isinstance(settings.get("packages"), list)
            assert not (profile / "extensions/supacode.ts").exists()
            bridge = json.loads((profile / "claude-bridge.json").read_text())
            assert bridge["provider"]["pathToClaudeCodeExecutable"] == str(home / ".nix-profile/bin/claude")
        assert not (personal / "extensions/usage-footer").exists()
        assert (home / ".config/claude-gmatter/agents").resolve() == home / ".config/claude-personal/agents"
        print("PASS portable MCP configuration, Claude bridge, and shared role links")


if __name__ == "__main__":
    main()
