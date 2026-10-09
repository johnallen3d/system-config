#!/usr/bin/env python3
"""Offline policy regressions; --installed verifies both work profiles and policy.

--record-before PATH records only hashes (0600), never settings/credentials.
--installed --before PATH additionally verifies preservation after activation.
--live-report PATH checks a pre-recorded audit for the ~14k context target.
No model calls, auth writes, or agent restarts.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "modules/home-manager/claude-work-context"
POLICY = json.loads((DIRECTORY / "policy.json").read_text())
spec = importlib.util.spec_from_file_location("context_merge", DIRECTORY / "merge.py")
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def preservation(home):
    settings = json.loads((home / ".config/claude-gmatter/settings.json").read_text())
    denies = settings.get("permissions", {}).get("deny", [])
    skills = settings.get("skillOverrides", {})
    unrelated = {k: v for k, v in settings.items() if k not in manager.CONTEXT_FLAGS}
    unrelated["permissions"] = {k: v for k, v in settings.get("permissions", {}).items() if k != "deny"}
    unrelated["skillOverrides"] = {k: v for k, v in skills.items() if k not in POLICY["skillOverrides"]}
    protected = {}
    for profile in ("claude-personal", "claude-gmatter"):
        for name in (".credentials.json", "auth.json"):
            path = home / ".config" / profile / name
            protected[f"{profile}/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    personal = home / ".config/claude-personal/settings.json"
    protected["personal_settings"] = digest(json.loads(personal.read_text())) if personal.exists() else None
    return {"unrelated_settings": digest(unrelated), "existing_denies": [digest(rule) for rule in denies], "protected": protected}


NATIVE_TOOLS = {"Task", "Bash", "Read", "Edit", "Write", "WebSearch", "WebFetch", "Skill"}


def check_live_report(report):
    baseline = report["baseline"]
    assert report["installed"]["work_profiles_verified"], "Audit used wrong profiles"
    assert baseline["actual_model"] == "claude-haiku-5-5", "Audit model differs"
    assert baseline["context_window"] == 1000000, "Audit window differs"
    assert 12000 <= baseline["initial_input_tokens"] <= 15000, "Work context is not approximately 14k"
    native = {name for name in baseline["tools"] if not name.startswith("mcp__")}
    assert native == NATIVE_TOOLS, "Native tool discovery differs from Mac"
    assert not (set(baseline["skills"]) & set(POLICY["skillOverrides"])), "Excluded skills remain advertised"
    assert not baseline["tool_calls"], "Audit unexpectedly called tools"
    assert all(server["status"] == "connected" for server in baseline["mcp_servers"]), "MCP startup failed"


def installed(before, live_report):
    home = Path.home()
    assert os.environ.get("PI_CODING_AGENT_DIR") == str(home / ".config/pi-work"), "Wrong Pi profile"
    assert os.environ.get("CLAUDE_CONFIG_DIR") == str(home / ".config/claude-gmatter"), "Wrong Claude profile"
    profile = home / ".config/claude-gmatter"
    assert json.loads((profile / "work-context-policy.json").read_text()) == POLICY, "Installed policy mismatch"
    settings = json.loads((profile / "settings.json").read_text())
    assert set(POLICY["permissions"]["deny"]) <= set(settings["permissions"]["deny"]), "Missing tool denies"
    assert all(settings["skillOverrides"].get(k) == v for k, v in POLICY["skillOverrides"].items()), "Missing skill policy"
    assert all(settings.get(k) == POLICY[k] for k in manager.CONTEXT_FLAGS), "Context flags differ from Mac policy"
    assert not (profile / "settings.json").is_symlink(), "Settings must remain writable"
    assert (profile / "settings.json").stat().st_mode & 0o777 == 0o600, "Settings must stay private"
    assert not (home / ".config/claude-personal/work-context-policy.json").exists(), "Policy leaked to personal profile"
    if before:
        old = json.loads(before.read_text())
        new = preservation(home)
        assert old["unrelated_settings"] == new["unrelated_settings"], "Unrelated work settings changed"
        assert old["protected"] == new["protected"], "Personal settings or credentials changed"
        assert set(old["existing_denies"]) <= set(new["existing_denies"]), "Existing permission restrictions removed"
    if live_report:
        check_live_report(json.loads(live_report.read_text()))
    print("Installed work-context policy and both profile variables verified" + ("; preservation verified" if before else "") + ("; ~14k runtime target verified" if live_report else ""))


class PolicyTests(unittest.TestCase):
    def test_mac_capability_boundary(self):
        manager.validate_policy(POLICY)
        denied = set(POLICY["permissions"]["deny"])
        self.assertEqual(len(denied), 31)
        self.assertTrue({"AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "EnterWorktree", "ExitWorktree", "NotebookEdit", "SendMessage", "CronCreate", "CronDelete", "CronList", "Workflow", "TaskStop", "mcp__claude_ai_Gmail"} <= denied)
        self.assertFalse({"Task", "Bash", "Read", "Edit", "Write", "WebSearch", "WebFetch", "Skill"} & denied)
        self.assertFalse(any(name.startswith("agent-kit:") for name in POLICY["skillOverrides"]))
        self.assertEqual(POLICY["skillOverrides"]["anthropic-skills:docs"], "off")
        self.assertIs(POLICY["disableBundledSkills"], True)
        for key in manager.CONTEXT_FLAGS - {"disableBundledSkills"}:
            self.assertIs(POLICY[key], False)

    def test_merge_preserves_every_other_field_and_is_idempotent(self):
        original = {"model": "saved-choice", "autoCompactEnabled": False, "autoMemoryEnabled": True,
                    "disableBundledSkills": True, "channelsEnabled": False,
                    "env": {"CLAUDE_CODE_DISABLE_1M_CONTEXT": "1", "PRIVATE": "secret"},
                    "hooks": {"SessionStart": [{"hooks": [{"command": "private hook"}]}]},
                    "permissions": {"deny": ["Bash(private:*)", "AskUserQuestion", "Artifact"], "allow": ["Read"], "defaultMode": "default"},
                    "skillOverrides": {"custom": "on", "design-sync": "on"}, "unknown": {"key": True}}
        merged = manager.merge(original, POLICY)
        self.assertEqual(merged, manager.merge(merged, POLICY))
        for key in original.keys() - {"permissions", "skillOverrides"} - manager.CONTEXT_FLAGS:
            self.assertEqual(merged[key], original[key])
        for key in manager.CONTEXT_FLAGS:
            self.assertEqual(merged[key], POLICY[key])
        self.assertIs(merged["autoMemoryEnabled"], False)
        self.assertIs(original["autoMemoryEnabled"], True)
        self.assertEqual(merged["permissions"]["deny"][:3], original["permissions"]["deny"])
        self.assertEqual(merged["permissions"]["deny"].count("Artifact"), 1)
        self.assertEqual(merged["permissions"]["allow"], ["Read"])
        self.assertEqual(merged["permissions"]["defaultMode"], "default")
        self.assertEqual(merged["skillOverrides"]["custom"], "on")
        self.assertEqual(original["skillOverrides"]["design-sync"], "on")

    def test_atomic_private_work_only_write_and_invalid_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            personal = home / ".config/claude-personal/settings.json"
            personal.parent.mkdir(parents=True)
            personal.write_text('{"private": "untouched"}')
            manager.apply(home, POLICY)
            work = home / ".config/claude-gmatter/settings.json"
            self.assertEqual(work.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(work.read_text()), manager.merge({}, POLICY))
            self.assertEqual(personal.read_text(), '{"private": "untouched"}')
            self.assertFalse(list(work.parent.glob("settings.json.context-*")))
            for content in ('invalid-json', '[]', '{"permissions": null}', '{"permissions":{"deny":"not-list"}}', '{"skillOverrides": null}'):
                work.write_text(content)
                with self.assertRaises(ValueError):
                    manager.apply(home, POLICY)
                self.assertEqual(work.read_text(), content)
            work.unlink()
            work.symlink_to(personal)
            with self.assertRaises(ValueError):
                manager.apply(home, POLICY)
            self.assertEqual(personal.read_text(), '{"private": "untouched"}')

    def test_rejects_auth_permission_bypass_and_unnamed_rules(self):
        for changed in ({"env": {"TOKEN": "private"}}, {"permissions": {"defaultMode": "bypassPermissions"}},
                        {"permissions": {"deny": ["Bash(secret)"]}},
                        {"skillOverrides": {"custom": "on"}}, {"model": "opus"},
                        {"autoMemoryEnabled": "false"}):
            with self.assertRaises(ValueError):
                manager.merge({}, POLICY | changed)

    def test_context_target_rejects_regressions(self):
        report = {"installed": {"work_profiles_verified": True}, "baseline": {
            "actual_model": "claude-haiku-5-5", "context_window": 1000000,
            "initial_input_tokens": 14000, "tools": sorted(NATIVE_TOOLS),
            "skills": ["agent-kit:authoring-commits"], "tool_calls": [],
            "mcp_servers": [{"status": "connected"}],
        }}
        check_live_report(report)
        for change in ({"initial_input_tokens": 31151}, {"context_window": 200000},
                       {"tools": sorted(NATIVE_TOOLS | {"Workflow"})},
                       {"skills": ["dataviz"]}, {"tool_calls": ["Read"]},
                       {"mcp_servers": [{"status": "failed"}]}):
            with self.assertRaises(AssertionError):
                check_live_report(report | {"baseline": report["baseline"] | change})

    def test_shared_import_and_activation_order(self):
        self.assertIn("./claude-work-context.nix", (ROOT / "modules/home-manager/agent-projects.nix").read_text())
        for module in ("default.nix", "coding-agents.nix"):
            self.assertIn("./agent-projects.nix", (ROOT / "modules/home-manager" / module).read_text())
        module = (ROOT / "modules/home-manager/claude-work-context.nix").read_text()
        self.assertIn('"claudeGmatterSettings"', module)
        self.assertIn('"claudeProfileDefaults"', module)
        self.assertIn("DRY_RUN_CMD", module)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--record-before", type=Path)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--live-report", type=Path)
    args = parser.parse_args()
    if (args.before or args.live_report) and not args.installed:
        parser.error("--before/--live-report require --installed")
    if args.record_before:
        fd = os.open(args.record_before, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(preservation(Path.home()), stream)
        print("Private preservation hashes recorded")
    elif args.installed:
        installed(args.before, args.live_report)
    else:
        unittest.main(argv=[__file__])


if __name__ == "__main__":
    main()
