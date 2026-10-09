#!/usr/bin/env python3
"""Audit installed work Claude context. No inference unless --live is supplied.

Run through `mise -C ~/dev/src/amfaro exec -- python3 /absolute/path/to/this.py`.
--live uses a disposable identical project, a fresh non-persisted session, the
work proxy, and a 1M window. Only sanitized inventories and token counts leave
the subprocess; never print prompts, replies, credentials, or provider errors.
--overlay accepts context policy only, not auth, hooks, or permission bypasses.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

FIXTURE = "Context audit fixture. Do not edit files or call tools.\n"
PROMPT = "Reply only OK. Do not use tools or skills."
TOKEN_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
SAFE_FLAGS = ("disableBundledSkills", "autoMemoryEnabled", "autoCompactEnabled", "channelsEnabled")


def overlay_policy(value):
    """Refuse accidental transfer of credentials or executable settings."""
    assert isinstance(value, dict)
    assert set(value) <= {"permissions", "skillOverrides", "disableBundledSkills", "autoMemoryEnabled"}
    for key in ("disableBundledSkills", "autoMemoryEnabled"):
        if key in value:
            assert isinstance(value[key], bool), key
    if "permissions" in value:
        permissions = value["permissions"]
        assert isinstance(permissions, dict) and set(permissions) == {"deny"}
        assert isinstance(permissions["deny"], list)
        assert all(isinstance(tool, str) and re.fullmatch(r"[\w:@.*-]+", tool)
                   for tool in permissions["deny"]), "Only tool-name denies are accepted"
    overrides = value.get("skillOverrides", {})
    assert isinstance(overrides, dict)
    assert all(isinstance(name, str) and re.fullmatch(r"[\w:@./-]+", name) and mode in ("on", "off")
               for name, mode in overrides.items())
    return value


def summarize(events, model):
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    messages = [e["message"] for e in events if e.get("type") == "assistant"
                and e.get("message", {}).get("model") != "<synthetic>"]
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    assert messages and not result.get("is_error", True), "Inference failed (details withheld)"
    assert messages[0]["model"] == model and model in result.get("modelUsage", {}), "Model fallback refused"
    calls = [b["name"] for message in messages for b in message.get("content", [])
             if b.get("type") == "tool_use"]
    assert not calls, "Unexpected tool call; baseline is not comparable"
    usage = messages[0]["usage"]
    window = result["modelUsage"][model]["contextWindow"]
    assert window == 1000000, "Effective window differs from the controlled 1M baseline"
    total = sum(usage.get(key, 0) or 0 for key in TOKEN_KEYS)
    return {
        "actual_model": messages[0]["model"], "context_window": window,
        "initial_input_tokens": total, "initial_input_percent": round(total / window * 100, 4),
        "initial_usage": {key: usage.get(key, 0) for key in (*TOKEN_KEYS, "output_tokens")},
        "tools": init.get("tools", []), "skills": init.get("skills", []),
        "mcp_servers": [{key: server.get(key) for key in ("name", "status", "source")}
                        for server in init.get("mcp_servers", [])],
        "plugins": [{key: plugin.get(key) for key in ("name", "source", "version")}
                    for plugin in init.get("plugins", [])],
        "cost_usd": result.get("total_cost_usd"), "tool_calls": calls,
    }


def installed(claude):
    home = Path.home()
    profile = home / ".config/claude-gmatter"
    assert os.environ.get("CLAUDE_CONFIG_DIR") == str(profile), "Select the work Claude profile via mise"
    assert os.environ.get("PI_CODING_AGENT_DIR") == str(home / ".config/pi-work"), "Select both work profiles"
    settings = json.loads((profile / "settings.json").read_text())
    manifest = json.loads((profile / "plugins/installed_plugins.json").read_text())
    instruction = (profile / "CLAUDE.md").read_bytes()
    hooks = settings.get("hooks", {})
    return {
        "platform": os.uname().sysname,
        "version": subprocess.check_output([claude, "--version"], text=True, timeout=30).strip(),
        "work_profiles_verified": True, "saved_model": settings.get("model"),
        "output_style": settings.get("outputStyle"),
        "context_flags": {key: settings.get(key) for key in SAFE_FLAGS},
        "inherited_1m_disable": os.environ.get("CLAUDE_CODE_DISABLE_1M_CONTEXT"),
        "inherited_experimental_disable": os.environ.get("CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS"),
        "tool_name_denies": [name for name in settings.get("permissions", {}).get("deny", [])
                            if re.fullmatch(r"[\w:@.*-]+", name)],
        "skill_overrides": settings.get("skillOverrides", {}),
        "instruction_bytes": len(instruction), "instruction_sha256": hashlib.sha256(instruction).hexdigest(),
        "hooks": {event: [{"type": hook.get("type"),
                           "command_sha256": hashlib.sha256(hook.get("command", "").encode()).hexdigest()}
                          for rule in rules for hook in rule.get("hooks", [])]
                  for event, rules in hooks.items()},
        "installed_plugins": [{"name": name, **{key: row.get(key)
                              for key in ("scope", "version", "gitCommitSha")},
                               "enabled": settings.get("enabledPlugins", {}).get(name, False)}
                              for name, rows in manifest["plugins"].items() for row in rows],
    }


def live(claude, model, overlay):
    env = dict(os.environ, CLAUDE_CODE_DISABLE_1M_CONTEXT="0", CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="1")
    # Never make the audit impersonate an active terminal pane through hooks.
    for key in list(env):
        if key.startswith(("HERDR_", "SUPACODE_")):
            env.pop(key)
    with tempfile.TemporaryDirectory(prefix=".context-audit-726-", dir=Path.home() / "dev/src/amfaro") as tmp:
        Path(tmp, "CLAUDE.md").write_text(FIXTURE)
        command = [claude, "--print", "--verbose", "--output-format", "stream-json",
                   "--no-session-persistence", "--model", model, "--max-budget-usd", "2", PROMPT]
        if overlay is not None:
            command += ["--settings", json.dumps(overlay_policy(overlay))]
        try:
            result = subprocess.run(command, cwd=tmp, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            raise AssertionError("Audit timed out (transcript withheld)") from None
        assert result.returncode == 0, "Claude failed (transcript withheld)"
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return {"fixture_sha256": hashlib.sha256(FIXTURE.encode()).hexdigest(),
                "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
                "overlay": overlay is not None, **summarize(events, model)}


class OfflineTests(unittest.TestCase):
    def test_policy_isolation(self):
        valid = {"permissions": {"deny": ["Workflow", "mcp__claude_ai_Gmail"]}, "disableBundledSkills": True}
        self.assertEqual(overlay_policy(valid), valid)
        for value in ({"env": {"ANTHROPIC_AUTH_TOKEN": "secret"}}, {"hooks": {}},
                      {"permissions": {"defaultMode": "bypassPermissions"}},
                      {"permissions": {"deny": ["Bash(curl --token secret)"]}},
                      {"disableBundledSkills": "false"}, {"skillOverrides": {"x": "invalid"}}):
            with self.assertRaises(AssertionError):
                overlay_policy(value)

    def test_usage_includes_both_caches_and_never_transcripts(self):
        model = "claude-haiku-5-5"
        events = [
            {"type": "system", "subtype": "init", "tools": ["Read"]},
            {"type": "assistant", "message": {"model": "<synthetic>"}},
            {"type": "assistant", "message": {"model": model, "content": [{"type": "text", "text": "SECRET"}],
                                               "usage": {"input_tokens": 10, "cache_creation_input_tokens": 20,
                                                         "cache_read_input_tokens": 30}}},
            {"type": "result", "is_error": False, "result": "SECRET",
             "modelUsage": {model: {"contextWindow": 1000000}}},
        ]
        summary = summarize(events, model)
        self.assertEqual(summary["initial_input_tokens"], 60)
        self.assertNotIn("SECRET", json.dumps(summary))
        events[-1]["modelUsage"][model]["contextWindow"] = 200000
        with self.assertRaises(AssertionError):
            summarize(events, model)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--live", action="store_true", help="Make one bounded work-proxy model turn")
    parser.add_argument("--claude", default="claude", help="Executable; can select a host-local matched version")
    parser.add_argument("--model", choices=("claude-haiku-5-5", "claude-opus-5-5"), default="claude-haiku-5-5")
    parser.add_argument("--overlay", type=Path, help="Temporary context-only JSON policy, never installed")
    args = parser.parse_args()
    if args.self_test:
        unittest.main(argv=[__file__])
        return
    if args.overlay and not args.live:
        parser.error("--overlay requires --live")
    overlay = overlay_policy(json.loads(args.overlay.read_text())) if args.overlay else None
    report = {"installed": installed(args.claude)}
    if args.live:
        report["baseline"] = live(args.claude, args.model, overlay)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit(str(error)) from None
