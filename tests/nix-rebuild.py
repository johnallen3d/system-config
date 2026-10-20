#!/usr/bin/env python3
"""Exercise rebuild routing and status with command mocks; never rebuild a host."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="nix-rebuild-test-") as directory:
        temp = Path(directory)
        repo = temp / "checkout with spaces"
        script = repo / ".mise/tasks/nix-rebuild"
        script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / ".mise/tasks/nix-rebuild", script)
        coordinator = repo / ".mise/scripts/deployment_state.py"
        coordinator.parent.mkdir(parents=True)
        coordinator.write_text("# routing-only stub; coordination is exercised in concurrent-deployments.py\n")
        commands = temp / "bin"
        commands.mkdir()
        capture = temp / "calls.jsonl"
        mock = commands / "mock"
        mock.write_text(f"#!{shutil.which('python3')}\n" + '''import json, os, sys
with open(os.environ["CAPTURE"], "a") as output:
    output.write(json.dumps({"command": os.path.basename(sys.argv[0]), "args": sys.argv[1:], "cwd": os.getcwd()}) + "\\n")
if os.path.basename(sys.argv[0]) == "sudo":
    sys.exit(int(os.environ.get("REBUILD_STATUS", "0")))
if os.path.basename(sys.argv[0]) == "nix":
    sys.exit(int(os.environ.get("UPDATE_STATUS", "0")))
''')
        mock.chmod(0o700)
        for command in ("nix", "sudo", "launchctl"):
            (commands / command).symlink_to(mock)
        base_env = dict(os.environ, PATH=f"{commands}:{os.environ['PATH']}", CAPTURE=str(capture),
                        SYSTEM_CONFIG_COORDINATED=str(repo), SYSTEM_CONFIG_SOURCE=str(repo))
        cases = [
            ({}, ["flake", "update"], 0),
            ({"usage_switch_only": "true"}, None, 0),
            ({"usage_picker_only": "true"}, ["flake", "update", "herdrProjectPicker"], 0),
            ({"usage_switch_only": "true", "REBUILD_STATUS": "7"}, None, 7),
            ({"usage_update_only": "true"}, ["flake", "update"], 0),
            ({"usage_update_only": "true", "usage_picker_only": "true"}, ["flake", "update", "herdrProjectPicker"], 0),
            ({"UPDATE_STATUS": "9"}, ["flake", "update"], 9),
            ({"usage_update_only": "true", "UPDATE_STATUS": "9"}, ["flake", "update"], 9),
        ]
        for variables, update, status in cases:
            capture.unlink(missing_ok=True)
            env = {key: value for key, value in base_env.items() if not key.startswith("usage_")}
            env.update(variables)
            result = subprocess.run(["bash", str(script)], cwd=temp, env=env, capture_output=True, text=True)
            assert result.returncode == status, result.stderr
            assert "nix-rebuild log:" in result.stderr
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            assert all(Path(call["cwd"]).resolve() == repo.resolve() for call in calls)
            updates = [call for call in calls if call["command"] == "nix"]
            assert [call["args"] for call in updates] == ([] if update is None else [update])
            rebuilds = [call for call in calls if call["command"] == "sudo"]
            should_build = variables.get("usage_update_only") != "true" and not variables.get("UPDATE_STATUS")
            assert len(rebuilds) == (1 if should_build else 0)
            if should_build:
                assert rebuilds[0]["args"][:-1] == ["-n", "/run/current-system/sw/bin/darwin-rebuild", "switch", "--impure", "--no-update-lock-file", "--no-write-lock-file", "--flake"]
                assert rebuilds[0]["args"][-1].startswith("path:")
                assert Path(rebuilds[0]["args"][-1].removeprefix("path:")).resolve() == repo.resolve()
            restarts = [call for call in calls if call["command"] == "launchctl"]
            assert len(restarts) == (1 if should_build and status == 0 else 0)
        capture.unlink(missing_ok=True)
        result = subprocess.run(["bash", str(script)], cwd=temp,
                                env=dict(base_env, usage_switch_only="true", usage_picker_only="true"),
                                capture_output=True, text=True)
        assert result.returncode == 2
        assert not capture.exists()
    print("PASS rebuild task: checkout routing, update modes, failure status, guarded restart")


if __name__ == "__main__":
    main()
