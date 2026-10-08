#!/usr/bin/env python3
"""Test footer resolution locally; --installed also checks activated work settings."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


SCRIPT = Path(__file__).resolve().parents[1] / "modules/home-manager/scripts/claude-work-statusline.sh"


def run(command, env, data="{}"):
    return subprocess.run(command, env=env, input=data, text=True,
                          capture_output=True, check=True, timeout=10).stdout


def main():
    with tempfile.TemporaryDirectory(prefix="claude footer ") as tmp:
        root = Path(tmp)
        profile = root / "work profile"
        plugins = profile / "plugins"
        plugins.mkdir(parents=True)
        manifest = plugins / "installed_plugins.json"
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(profile),
                   PI_CODING_AGENT_DIR=str(root / "pi-work"))
        command = ["bash", str(SCRIPT)]
        assert run(command, env) == ""  # No plugin provisioned yet.
        manifest.write_text(json.dumps({"plugins": {}}))
        assert run(command, env) == ""
        plugin = plugins / "cache/amfaro/agent-kit/0.55.0"
        renderer = plugin / "claude-code/statusline.mjs"
        renderer.parent.mkdir(parents=True)
        renderer.write_text("process.stdin.pipe(process.stdout);\n")
        # A newer cache entry must not override the actually installed version.
        newer = plugins / "cache/amfaro/agent-kit/99.0.0/claude-code/statusline.mjs"
        newer.parent.mkdir(parents=True)
        newer.write_text("throw new Error('wrong cached version');\n")
        manifest.write_text(json.dumps({"plugins": {"agent-kit@amfaro": [
            {"scope": "project", "installPath": str(newer.parent.parent)},
            {"scope": "user", "installPath": str(plugin)},
        ]}}))
        assert run(command, env, '{"probe":"stdin intact"}') == '{"probe":"stdin intact"}'
        renderer.unlink()
        assert run(command, env) == ""
        print("PASS profile-local installed plugin selection, spaced paths, stdin, missing-plugin handling")

    if "--installed" in sys.argv:
        profile = Path.home() / ".config/claude-gmatter"
        settings = json.loads((profile / "settings.json").read_text())
        status = settings["statusLine"]
        assert status["type"] == "command" and status["padding"] == 0
        assert "/nix/store/" in status["command"] and "/Users/" not in status["command"]
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(profile),
                   PI_CODING_AGENT_DIR=str(Path.home() / ".config/pi-work"), NO_COLOR="1")
        data = {"model": {"display_name": "Claude Opus"},
                "context_window": {"context_window_size": 200000,
                                   "used_percentage": 25,
                                   "current_usage": {"input_tokens": 50000}},
                "workspace": {"current_dir": str(SCRIPT.parents[3])}}
        output = run(["bash", "-c", status["command"]], env, json.dumps(data))
        assert "ctx 50k/200k 25%" in output and "Claude Opus" in output, output
        assert SCRIPT.parents[3].name in output, output
        print("PASS installed work footer renders context, model, and working directory")


if __name__ == "__main__":
    main()
