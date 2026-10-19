#!/usr/bin/env python3
"""Verify installed Claude proxy/picker; --live makes bounded streaming/tool calls.

Use --profile personal in personal context, or work (default) through work mise on each host. Never emits keys, request bodies,
provider errors, or raw Claude transcripts; no sessions are persisted.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"scout": "haiku", "researcher": "haiku", "planner": "opus", "worker": "opus", "reviewer": "opus"}
ALIASES = {"haiku": "claude-haiku-5-5", "opus": "claude-opus-5-5",
           "sonnet": "claude-sonnet-5-5", "fable": "claude-fable-5-1"}

MODELS = {
    "claude-haiku-5-5": "Claude Haiku 5.5",
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-fable-5-1": "Claude Fable 5.1",
    "gpt-6-luna": "Codex 6 Luna",
    "gpt-6.1-sol": "Codex 6.1 Sol",
    "gpt-6-astra": "Codex 6 Astra",
}

PERSONAL_ALIASES = dict(ALIASES)
PERSONAL_MODELS = {**MODELS, "claude-sonnet-5-5": "Claude Sonnet 5.5"}
PROFILE = "work"
PERSONAL_BEHAVES_AS = "claude-sonnet-4-6"
PERSONAL_CONTEXT_WINDOW = 200000


def assert_no_catalog_warning(output):
    assert "isn't described by this version's model catalog" not in output, "Unknown-model catalog startup warning"


def role_models(directory):
    models = {}
    for role in ROLES:
        text = (directory / f"{role}.md").read_text()
        assert text.startswith("---\n"), f"{role}: missing frontmatter"
        header = text.split("---", 2)[1]
        rows = [line.split(":", 1)[1].strip() for line in header.splitlines() if line.startswith("model:")]
        assert rows == [ROLES[role]], f"{role}: must use managed {ROLES[role]} alias, not a hard-coded model ID"
        models[role] = rows[0]
    return models


def validate_catalog(env, picker, available):
    required = {env[f"ANTHROPIC_DEFAULT_{alias.upper()}_MODEL"] for alias in ALIASES}
    required.update(row["model"] for row in picker["options"])
    required.update(env[key] for key in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_MODEL", "ANTHROPIC_SMALL_FAST_MODEL") if key in env)
    missing = required - set(available)
    assert not missing, "Gateway does not advertise configured Claude Code models: " + ", ".join(sorted(missing))


def installed():
    home = Path.home()
    pi_dir = "pi" if PROFILE == "personal" else "pi-work"
    claude_dir = "claude-personal" if PROFILE == "personal" else "claude-gmatter"
    prefix = "personalClaude" if PROFILE == "personal" else "claude"
    assert os.environ.get("PI_CODING_AGENT_DIR") == str(home / ".config" / pi_dir), "Wrong Pi profile context"
    assert os.environ.get("CLAUDE_CONFIG_DIR") == str(home / ".config" / claude_dir), "Wrong Claude profile context"
    root = home / ".config/subscription-proxy"
    settings = json.loads((home / ".config" / claude_dir / "settings.json").read_text())
    selected = json.loads((root / "selected.json").read_text())
    credentials = json.loads((root / "credentials.json").read_text())["profiles"][PROFILE]
    endpoint = json.loads((root / "endpoints.json").read_text())[PROFILE]
    env = settings["env"]
    assert env["ANTHROPIC_BASE_URL"] == endpoint
    assert env["ANTHROPIC_AUTH_TOKEN"] == credentials["client"]
    assert env["ANTHROPIC_API_KEY"] == ""
    for alias, model in ALIASES.items():
        key = f"ANTHROPIC_DEFAULT_{alias.upper()}_MODEL"
        assert env[key] == model, f"Unexpected managed {alias} target"
        assert os.environ.get(key, model) == model, f"Inherited environment overrides managed {alias} target"
    assert not os.environ.get("CLAUDE_CODE_SUBAGENT_MODEL"), "Inherited subagent model override needs review"
    assert not env.get("CLAUDE_CODE_SUBAGENT_MODEL"), "Settings subagent model override needs review"
    role_models(ROOT / "modules/home-manager/claude-agents")
    role_models(home / ".config" / claude_dir / "agents")
    picker = settings["modelPicker"]
    assert picker["replaceBuiltInOptions"] is True
    assert {row["model"]: row["label"] for row in picker["options"]} == MODELS
    assert selected[prefix] is True and selected[prefix + "Picker"] == picker
    if PROFILE == "personal":
        assert "ANTHROPIC_MODEL" not in env and not os.environ.get("ANTHROPIC_MODEL"), "Forced model overrides saved /model choice"
        assert env["ANTHROPIC_DEFAULT_MODEL"] == env["ANTHROPIC_SMALL_FAST_MODEL"] == "gpt-6-luna"
        for key in ("ANTHROPIC_DEFAULT_MODEL", "ANTHROPIC_SMALL_FAST_MODEL"):
            assert os.environ.get(key, env[key]) == env[key], f"Inherited {key} overrides personal routing"
        assert all(row.get("behavesAs") == PERSONAL_BEHAVES_AS if row["model"].startswith("gpt-")
                   else "behavesAs" not in row for row in picker["options"])
        for key in ("DISABLE_COMPACT", "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT", "CLAUDE_CODE_DISABLE_1M_CONTEXT", "CLAUDE_CODE_MAX_CONTEXT_TOKENS"):
            assert not env.get(key) and not os.environ.get(key), f"Unexpected context/compaction override: {key}"
    version = subprocess.check_output(["claude", "--version"], text=True).split()[0]
    assert tuple(map(int, version.split("."))) >= (2, 1, 293), "Claude too old for Haiku 5.5"
    sys.path.insert(0, str(ROOT / "modules/home-manager/subscription-proxy"))
    import manager
    available = {row["id"] for row in manager.request(PROFILE, "/v1/models", management=False).get("data", [])}
    validate_catalog(env, picker, available)
    if PROFILE == "personal":
        definitions = manager.request(PROFILE, "/routing/model-definitions/codex").get("models", [])
        windows = {row["id"]: row.get("context_length", 0) for row in definitions}
        assert all(windows.get(model, 0) >= PERSONAL_CONTEXT_WINDOW for model in MODELS if model.startswith("gpt-")), "Compatibility window exceeds gateway catalog limit"
    print(f"PASS installed: {PROFILE} profiles/auth, five role aliases, all alias targets and {len(MODELS)} picker IDs advertised by live CLIProxyAPI (Claude {version}); no inference")


def live(model, use_default=False):
    with tempfile.TemporaryDirectory(prefix="claude-proxy-smoke-") as directory:
        marker = "PROXY_TOOL_" + secrets.token_hex(8)
        Path(directory, "marker.txt").write_text(marker + "\n")
        command = [
            "claude", "--print", "--verbose", "--output-format", "stream-json",
            "--include-partial-messages", "--no-session-persistence",
            *([] if use_default else ["--model", model]),
            "--tools", "Read", "--allowedTools", "Read",
            "--disable-slash-commands", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--setting-sources", "user", "--max-budget-usd", "1",
            "Use the Read tool to read marker.txt in the current directory. "
            "Then reply only with its exact contents. You must call Read before replying.",
        ]
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{model}: Claude Code timeout (transcript withheld)") from None
        if PROFILE == "personal":
            assert_no_catalog_warning(result.stderr + result.stdout)
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        outcome = next((event for event in reversed(events) if event.get("type") == "result"), {})
        tool = any(block.get("type") == "tool_use" and block.get("name") == "Read"
                   for event in events if event.get("type") == "assistant"
                   for block in event.get("message", {}).get("content", []))
        streaming = any(event.get("type") == "stream_event" for event in events)
        used = outcome.get("modelUsage", {})
        assert result.returncode == 0 and not outcome.get("is_error", True), f"{model}: inference failed (details withheld)"
        assert tool and streaming, f"{model}: missing actual Read tool call or streaming"
        assert marker in outcome.get("result", ""), f"{model}: tool result was not returned"
        assert model in used, f"{model}: requested model not reported in usage; refusing fallback"
        if PROFILE == "personal" and model.startswith("gpt-"):
            assert used[model].get("contextWindow") == PERSONAL_CONTEXT_WINDOW, f"{model}: unsafe or unexpected client context window"
        print(f"PASS live {model}: actual Claude Code streaming, Read tool execution, exact model usage, no persisted session")


def live_subagent(role):
    """Exercise actual Agent dispatch, with different parent/child model families."""
    expected = ALIASES[ROLES[role]]
    parent = ALIASES["opus" if ROLES[role] == "haiku" else "haiku"]
    with tempfile.TemporaryDirectory(prefix="claude-subagent-smoke-") as directory:
        marker = "SUBAGENT_TOOL_" + secrets.token_hex(8)
        Path(directory, "marker.txt").write_text(marker + "\n")
        command = [
            "claude", "--print", "--verbose", "--output-format", "stream-json",
            "--include-partial-messages", "--forward-subagent-text", "--no-session-persistence",
            "--model", parent, "--tools", "Agent,Read", "--allowedTools", f"Agent({role}),Read",
            "--disable-slash-commands", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--setting-sources", "user", "--max-budget-usd", "1",
            f"This is a read-only subagent routing smoke test. Call Agent exactly once with subagent_type={role}. "
            "Run it synchronously, not in the background. Do not set its model: use the installed role definition. "
            "Ask it to call Read on marker.txt "
            "in the current directory and return its exact contents. Do not read the file yourself. "
            "No research, edits, shell commands, or other tasks. Return the marker from the subagent.",
        ]
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{role}: subagent timeout (transcript withheld)") from None
        if PROFILE == "personal":
            assert_no_catalog_warning(result.stderr + result.stdout)
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        outcome = next((event for event in reversed(events) if event.get("type") == "result"), {})
        dispatches = [block for event in events if event.get("type") == "assistant"
                      for block in event.get("message", {}).get("content", [])
                      if block.get("type") == "tool_use" and block.get("name") == "Agent"]
        assert len(dispatches) == 1, f"{role}: expected exactly one actual Agent dispatch"
        inputs = dispatches[0].get("input", {})
        assert inputs.get("subagent_type") == role and "model" not in inputs, f"{role}: role/model selection overridden"
        child_read = any(event.get("parent_tool_use_id") == dispatches[0]["id"]
                         and block.get("type") == "tool_use" and block.get("name") == "Read"
                         for event in events if event.get("type") == "assistant"
                         for block in event.get("message", {}).get("content", []))
        assert result.returncode == 0 and not outcome.get("is_error", True), f"{role}: subagent inference failed (details withheld)"
        assert child_read, f"{role}: missing actual child Read tool call"
        # Judge the actual child's Read result, not the parent's ELI5 summary:
        # some role/parent combinations paraphrase a successful child response.
        child_result = any(event.get("parent_tool_use_id") == dispatches[0]["id"]
                           and block.get("type") == "tool_result" and not block.get("is_error")
                           and marker in json.dumps(block.get("content", ""))
                           for event in events if event.get("type") == "user"
                           for block in event.get("message", {}).get("content", []))
        assert child_result, f"{role}: child did not receive the actual Read marker"
        assert all(not event.get("is_error") for event in events if event.get("type") == "result"), f"{role}: a parent/child result failed"
        assert expected in outcome.get("modelUsage", {}), f"{role}: managed {expected} absent from usage; refusing fallback"
        print(f"PASS live subagent {role}: actual Agent dispatch and child Read, {expected} usage through {PROFILE} proxy, no persisted session")


def main():
    global PROFILE, ALIASES, MODELS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("personal", "work"), default="work")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--live-default", action="store_true", help="Test personal default without --model")
    parser.add_argument("--model", choices=PERSONAL_MODELS, action="append")
    parser.add_argument("--live-subagent", choices=ROLES, action="append",
                        help="Make a bounded actual Agent dispatch with the installed role (repeatable)")
    args = parser.parse_args()
    PROFILE = args.profile
    if PROFILE == "personal":
        ALIASES, MODELS = PERSONAL_ALIASES, PERSONAL_MODELS
    if any(model not in MODELS for model in args.model or []):
        parser.error("Live checks accept only the selected profile's curated models")
    installed()
    if args.live_default:
        if PROFILE != "personal":
            parser.error("--live-default is scoped to personal routing")
        settings = json.loads((Path.home() / ".config/claude-personal/settings.json").read_text())
        saved = settings.get("model")
        expected = PERSONAL_ALIASES.get(saved, saved) if saved and saved != "default" else "gpt-6-luna"
        assert expected in PERSONAL_MODELS, "Saved personal model needs an explicit curated-route review"
        live(expected, use_default=True)
    if args.live:
        for model in args.model or MODELS:
            live(model)
    for role in args.live_subagent or []:
        live_subagent(role)


if __name__ == "__main__":
    main()
