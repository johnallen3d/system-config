#!/usr/bin/env python3
"""Exercise generated Pi activation scripts in temporary profiles, never live ones.

Run: python3 tests/pi-settings.py
Requires Nix and this repository's locked flake inputs; does not call Pi/models.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def activation_scripts():
    expression = """
      let
        flake = builtins.getFlake %s;
        home = flake.darwinConfigurations.m4-mbp.config.home-manager.users."john.allen";
        activation = home.home.activation;
      in {
        scripts = builtins.listToAttrs (map (name: {
          inherit name;
          value = activation.${name}.data;
        }) ["piSettings" "piWorkSettings" "piNotesSettings" "piClaudeBridgeCleanup"]);
        activationNames = builtins.attrNames activation;
        managedFiles = builtins.attrNames home.home.file;
      }
    """ % json.dumps(str(ROOT))
    result = subprocess.run(
        ["nix", "eval", "--impure", "--json", "--expr", expression],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def run(script, home, dry_run=False):
    env = dict(os.environ, HOME=str(home), PI_CODING_AGENT_DIR=str(home / ".config/pi"))
    env.pop("DRY_RUN", None)
    if dry_run:
        env["DRY_RUN"] = "1"
    subprocess.run(
        ["bash", "-euc", script], env=env, check=True,
        capture_output=True, text=True,
    )


def main():
    configuration = activation_scripts()
    scripts = configuration["scripts"]
    assert "piClaudeBridgeSettings" not in configuration["activationNames"]
    assert "piWorkClaudeBridgeSettings" not in configuration["activationNames"]
    assert not any("issue-implement-claude" in name for name in configuration["managedFiles"])
    with tempfile.TemporaryDirectory(prefix="pi-settings-") as tmp:
        home = Path(tmp)
        for name, profile in (
            ("piSettings", "pi"),
            ("piWorkSettings", "pi-work"),
            ("piNotesSettings", "pi-notes"),
        ):
            script = scripts[name]
            path = home / ".config" / profile / "settings.json"
            run(script, home, dry_run=True)
            assert not path.parent.exists(), "Dry run must not create directories"
            run(script, home)
            defaults = json.loads(path.read_text())
            assert "lastChangelogVersion" not in defaults
            assert defaults["defaultModel"] == "gpt-6.1-sol"
            if profile == "pi-work":
                assert "extensions" not in defaults, "Removed work extensions must stay absent"
                assert defaults["defaultProjectTrust"] == "always"
                assert len(defaults["subagents"]["agentOverrides"]) == 8
                assert defaults["subagents"]["agentOverrides"]["scout"] == {
                    "model": "opencode-go/deepseek-v4-flash", "thinking": "off",
                }

            # Simulate Pi writes and formerly managed keys, including nested drift.
            old = dict(defaults, lastChangelogVersion="runtime-version",
                       extensions=["-builtin:mcp", "stale-extension"],
                       defaultModel="runtime-model", unknownSetting=True,
                       compaction={"enabled": True, "unknownNestedKey": True},
                       subagents={"agentOverrides": {"obsolete-agent": {"model": "stale"}}},
                       mcpServers={"stale": {}})
            path.write_text(json.dumps(old))
            original = path.read_bytes()
            run(script, home, dry_run=True)
            assert path.read_bytes() == original, "Dry run must not modify settings"
            run(script, home)
            expected = dict(defaults, lastChangelogVersion="runtime-version")
            assert json.loads(path.read_text()) == expected, profile
            assert not path.is_symlink() and os.access(path, os.W_OK)
            original = path.read_bytes()
            run(script, home)
            assert path.read_bytes() == original, "Activation must be idempotent"

            # Missing/malformed/non-object/multiple-document JSON all restore defaults.
            for invalid in ("{broken", "[]", "null", '"text"', "{}\n{}", ""):
                path.write_text(invalid)
                run(script, home)
                assert json.loads(path.read_text()) == defaults
                assert path.with_suffix(".json.invalid.bak").read_text() == invalid
            path.unlink()
            run(script, home)
            assert json.loads(path.read_text()) == defaults
            assert not list(path.parent.glob("settings.json.tmp.*"))
            print(f"PASS {profile}: authoritative writable settings, runtime allowlist, removal, recovery, dry run, idempotence")

        bridges = [home / ".config" / profile / "claude-bridge.json"
                   for profile in ("pi", "pi-work", "pi-notes")]
        for path in bridges[:2]:
            path.write_text("retired settings")
        bridges[2].symlink_to(bridges[0])
        # Cleanup must touch neither authentication nor session data.
        for profile in ("pi", "pi-work", "pi-notes"):
            directory = home / ".config" / profile
            (directory / "auth.json").write_text("sentinel auth")
            (directory / "sessions").mkdir()
            (directory / "sessions/sentinel.jsonl").write_text("sentinel session")
        cleanup = scripts["piClaudeBridgeCleanup"]
        run(cleanup, home, dry_run=True)
        assert all(path.exists() for path in bridges)
        run(cleanup, home)
        run(cleanup, home)
        assert not any(os.path.lexists(path) for path in bridges)
        for profile in ("pi", "pi-work", "pi-notes"):
            directory = home / ".config" / profile
            assert (directory / "auth.json").read_text() == "sentinel auth"
            assert (directory / "sessions/sentinel.jsonl").read_text() == "sentinel session"
            assert (directory / "settings.json").exists()
        print("PASS retired bridge config/prompt removal, dry run, and untouched auth/sessions")


if __name__ == "__main__":
    main()
