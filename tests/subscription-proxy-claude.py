#!/usr/bin/env python3
"""Verify installed work Claude proxy/picker; --live makes bounded streaming/tool calls.

Run through the work mise context on each host. Never emits keys, request bodies,
provider errors, or raw Claude transcripts; no sessions are persisted.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

MODELS = {
    "claude-haiku-5-5": "Claude Haiku 5.5",
    "claude-opus-5-5": "Claude Opus 5.5",
    "claude-fable-5-1": "Claude Fable 5.1",
    "gpt-6-luna": "Codex 6 Luna",
    "gpt-6.1-sol": "Codex 6.1 Sol",
    "gpt-6-astra": "Codex 6 Astra",
}


def installed():
    home = Path.home()
    assert os.environ.get("PI_CODING_AGENT_DIR") == str(home / ".config/pi-work"), "Wrong Pi profile context"
    assert os.environ.get("CLAUDE_CONFIG_DIR") == str(home / ".config/claude-gmatter"), "Wrong Claude profile context"
    root = home / ".config/subscription-proxy"
    settings = json.loads((home / ".config/claude-gmatter/settings.json").read_text())
    selected = json.loads((root / "selected.json").read_text())
    credentials = json.loads((root / "credentials.json").read_text())["profiles"]["work"]
    endpoint = json.loads((root / "endpoints.json").read_text())["work"]
    env = settings["env"]
    assert env["ANTHROPIC_BASE_URL"] == endpoint
    assert env["ANTHROPIC_AUTH_TOKEN"] == credentials["client"]
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "claude-opus-5-5"
    assert env["ANTHROPIC_DEFAULT_FABLE_MODEL"] == "claude-fable-5-1"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "claude-haiku-5-5"
    picker = settings["modelPicker"]
    assert picker["replaceBuiltInOptions"] is True
    assert {row["model"]: row["label"] for row in picker["options"]} == MODELS
    assert selected["claude"] is True and selected["claudePicker"] == picker
    version = subprocess.check_output(["claude", "--version"], text=True).split()[0]
    assert tuple(map(int, version.split("."))) >= (2, 1, 293), "Claude too old for Haiku 5.5"
    print(f"PASS installed: work profiles, proxy client auth, pinned aliases, six labeled picker models (Claude {version})")


def live(model):
    with tempfile.TemporaryDirectory(prefix="claude-proxy-smoke-") as directory:
        marker = "PROXY_TOOL_" + secrets.token_hex(8)
        Path(directory, "marker.txt").write_text(marker + "\n")
        command = [
            "claude", "--print", "--verbose", "--output-format", "stream-json",
            "--include-partial-messages", "--no-session-persistence",
            "--model", model, "--tools", "Read", "--allowedTools", "Read",
            "--disable-slash-commands", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--setting-sources", "user", "--max-budget-usd", "1",
            "Use the Read tool to read marker.txt in the current directory. "
            "Then reply only with its exact contents. You must call Read before replying.",
        ]
        try:
            result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            raise AssertionError(f"{model}: Claude Code timeout (transcript withheld)") from None
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
        print(f"PASS live {model}: actual Claude Code streaming, Read tool execution, exact model usage, no persisted session")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", choices=MODELS, action="append")
    args = parser.parse_args()
    installed()
    if args.live:
        for model in args.model or MODELS:
            live(model)


if __name__ == "__main__":
    main()
