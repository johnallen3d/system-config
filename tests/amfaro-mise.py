#!/usr/bin/env python3
"""Test directory-selected agent profiles without models, installs, or credentials.

Default: disposable home using the tracked config. --installed: current home.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

CONFIG = Path(__file__).resolve().parents[1] / "modules/home-manager/agent-projects/amfaro-mise.toml"
KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY")


def check(home, mise, env, tmp):
    work = home / "dev/src/amfaro"
    nested = work / "system-config-profile-test"
    # No need to create a real project: mise -C accepts a directory only.
    # Installed checks use the existing parent to avoid touching project trees.
    if home == Path(tmp) / "home":
        nested.mkdir(parents=True)
    else:
        nested = next((p for p in work.iterdir() if p.is_dir()), work)
    probe = Path(tmp) / "probe.py"
    probe.write_text(
        "import json, os, sys\n"
        "print(json.dumps({'pi': os.getenv('PI_CODING_AGENT_DIR'), "
        "'claude': os.getenv('CLAUDE_CONFIG_DIR'), "
        "'jev_mode': os.getenv('PI_MODEL_ROUTER_JEV_MODE'), "
        "'keys': [os.getenv(k) for k in " + repr(KEYS) + "], 'args': sys.argv[1:]}))\n"
    )
    env = dict(env, MISE_EXEC_AUTO_INSTALL="false", MISE_AUTO_INSTALL="false",
               PI_CODING_AGENT_DIR=str(home / ".config/pi"),
               CLAUDE_CONFIG_DIR=str(home / ".config/claude-personal"),
               PI_MODEL_ROUTER_JEV_MODE="fallback",
               **{key: "test-key" for key in KEYS})
    for directory, profile in ((work, "work"), (nested, "work"), (home, "personal")):
        args = ["--test", "argument with spaces"]
        result = subprocess.run(
            [mise, "-C", str(directory), "exec", "--", sys.executable, str(probe), *args],
            env=env, check=True, capture_output=True, text=True, timeout=30,
        )
        actual = json.loads(result.stdout)
        assert actual == {
            "pi": str(home / ".config" / ("pi-work" if profile == "work" else "pi")),
            "claude": str(home / ".config" / ("claude-gmatter" if profile == "work" else "claude-personal")),
            "jev_mode": "primary" if profile == "work" else "fallback",
            "keys": [""] * 3 if profile == "work" else ["test-key"] * 3,
            "args": args,
        }, (directory, actual)
        print(f"PASS {directory}: {profile} paired profiles, JEV mode, API-key isolation, arguments intact")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    options = parser.parse_args()
    mise = shutil.which("mise")
    assert mise, "mise must be installed"
    config = tomllib.loads(CONFIG.read_text())
    assert set(config) == {"env"}, "Project tools/dependencies must stay project-owned"
    for key in KEYS:
        assert config["env"][key] == {"value": "", "tools": False}
    with tempfile.TemporaryDirectory() as tmp:
        if options.installed:
            home = Path.home()
            installed = home / "dev/src/amfaro/mise.toml"
            assert installed.is_symlink(), "Expected Home Manager ownership"
            assert installed.read_text() == CONFIG.read_text()
            check(home, mise, os.environ, tmp)
        else:
            home = Path(tmp) / "home"
            work = home / "dev/src/amfaro"
            work.mkdir(parents=True)
            managed = Path(tmp) / "managed-mise.toml"
            managed.write_text(CONFIG.read_text())
            (work / "mise.toml").symlink_to(managed)
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("MISE_", "__MISE"))}
            env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                       XDG_DATA_HOME=str(home / ".local/share"),
                       XDG_CACHE_HOME=str(home / ".cache"), MISE_PARANOID="1")
            subprocess.run([mise, "trust", str(work / "mise.toml")], env=env,
                           check=True, capture_output=True, text=True, timeout=30)
            check(home, mise, env, tmp)


if __name__ == "__main__":
    main()
