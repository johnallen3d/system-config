#!/usr/bin/env python3
"""Check the actual Mac/Omarchy MCP activation merge without model calls.

Default: evaluate both hosts and run their activation in isolated homes.
--record-before PATH / --installed --before PATH check installed preservation.
Only hashes of protected configuration and credentials are recorded.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SLACK = {
    "type": "http", "url": "https://mcp.slack.com/mcp",
    "oauth": {"clientId": "1601185624273.8899143856786", "callbackPort": 3118},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def preservation():
    home = Path.home()
    config = json.loads((home / ".config/claude-gmatter/.claude.json").read_text())
    result = {"other_servers": digest({k: v for k, v in config.get("mcpServers", {}).items()
                                       if k != "slack"})}
    for profile in ("claude-personal", "claude-gmatter"):
        names = [".credentials.json", "auth.json"]
        if profile == "claude-personal":
            names += [".claude.json", "settings.json"]
        for name in names:
            path = home / ".config" / profile / name
            result[f"{profile}/{name}"] = (hashlib.sha256(path.read_bytes()).hexdigest()
                                           if path.exists() else None)
    return result


def installed(before):
    home = Path.home()
    assert os.environ.get("CLAUDE_CONFIG_DIR") == str(home / ".config/claude-gmatter")
    assert os.environ.get("PI_CODING_AGENT_DIR") == str(home / ".config/pi-work")
    path = home / ".config/claude-gmatter/.claude.json"
    assert not path.is_symlink(), "Runtime config must remain writable"
    assert path.stat().st_mode & 0o777 == 0o600, "Runtime config must remain private"
    assert json.loads(path.read_text())["mcpServers"]["slack"] == SLACK
    if before:
        assert preservation() == json.loads(before.read_text()), "Protected state changed"
    print("PASS installed work Slack registration, profile isolation" +
          (", other MCP servers and credentials preserved" if before else ""))


def evaluate():
    attributes = (
        'darwinConfigurations.m4-mbp.config.home-manager.users."john.allen"',
        'homeConfigurations."johna@omarchy".config',
    )
    for attribute in attributes:
        script = subprocess.check_output([
            "nix", "--extra-experimental-features", "nix-command flakes", "eval",
            "--impure", "--raw", "--no-write-lock-file",
            f"path:{ROOT}#{attribute}.home.activation.claudeGmatterMcp.data",
        ], text=True, timeout=180)
        # Cross-platform evaluation only: execute with this host's native tools.
        native_path = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep)
                                      if "/shims" not in p)
        for tool in ("jq", "mktemp"):
            executable = shutil.which(tool, path=native_path)
            assert executable, f"Missing {tool}"
            script = re.sub(r"/nix/store/[^\s\"/]+/bin/" + tool, executable, script)
        with tempfile.TemporaryDirectory(prefix="claude-mcp-test-") as tmp:
            home = Path(tmp)
            empty = home / "empty.json"
            empty.write_text("{}")
            script = re.sub(r"/nix/store/[^\s]+-claude-empty-config.json", str(empty), script)
            path = home / ".config/claude-gmatter/.claude.json"
            personal = home / ".config/claude-personal/.claude.json"
            personal.parent.mkdir(parents=True)
            personal.write_text('{"mcpServers":{"private":{"url":"keep"}}}')
            credentials = path.parent / ".credentials.json"
            credentials.parent.mkdir(parents=True)
            credentials.write_text('{"oauth":"machine-local"}')
            original = {"mcpServers": {"headroom": {"command": "keep"},
                                      "slack": {"url": "stale", "headers": {"obsolete": "remove"}}},
                        "projects": {"/work": {"trust": True}}, "unknown": ["keep"]}
            path.write_text(json.dumps(original))
            env = dict(os.environ, HOME=tmp, PATH=native_path, DRY_RUN_CMD="echo")

            def run(ok=True):
                result = subprocess.run(["bash", "-eu", "-c", script], env=env,
                                        capture_output=True, text=True, timeout=20)
                assert (result.returncode == 0) == ok, result.stderr
                assert not list(path.parent.glob(".claude.json.mcp-*")), "Temporary file leaked"

            run()
            assert json.loads(path.read_text()) == original, "Dry run wrote config"
            env["DRY_RUN_CMD"] = ""
            run()
            expected = dict(original, mcpServers=dict(original["mcpServers"], slack=SLACK))
            assert json.loads(path.read_text()) == expected
            assert path.stat().st_mode & 0o777 == 0o600
            once = path.read_bytes()
            run()
            assert path.read_bytes() == once, "Merge is not idempotent"
            for initial in ('{}', '{"mcpServers":{}}'):
                path.write_text(initial)
                run()
                assert json.loads(path.read_text()) == {"mcpServers": {"slack": SLACK}}
            path.unlink()
            run()
            assert json.loads(path.read_text()) == {"mcpServers": {"slack": SLACK}}
            for invalid in ('invalid-json', '[]', 'null', '{"mcpServers":null}',
                            '{"mcpServers":[]}', '{"mcpServers":false}'):
                path.write_text(invalid)
                run(ok=False)
                assert path.read_text() == invalid, "Invalid config was overwritten"
            path.unlink()
            path.symlink_to(personal)
            run(ok=False)
            assert path.is_symlink()
            assert personal.read_text() == '{"mcpServers":{"private":{"url":"keep"}}}'
            assert credentials.read_text() == '{"oauth":"machine-local"}'
        print(f"PASS {attribute}: actual activation, preservation, idempotence, dry run, invalid input, symlinks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--record-before", type=Path)
    parser.add_argument("--before", type=Path)
    args = parser.parse_args()
    if args.before and not args.installed:
        parser.error("--before requires --installed")
    if args.record_before:
        fd = os.open(args.record_before, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(preservation(), stream)
        print("Recorded private preservation hashes")
    elif args.installed:
        installed(args.before)
    else:
        evaluate()


if __name__ == "__main__":
    main()
