"""Run on the Mac inside Herdr; creates/closes only its own remote test workspace.

No model prompts or account changes. Checks remote routing, shell setup,
process persistence across separate SSH API connections, and Pi detection.
"""

import json
import os
import subprocess
import time

assert os.environ.get("HERDR_ENV") == "1", "Run from a Herdr-managed pane"


def call(*args, raw=False):
    result = subprocess.run(
        ["herdr", "--machine", "Omarchy", *args],
        capture_output=True,
        text=True,
        timeout=90,
        check=True,
    )
    if raw or not result.stdout.lstrip().startswith("{"):
        return result.stdout
    return json.loads(result.stdout)["result"]


created = call(
    "workspace",
    "create",
    "--cwd",
    "/home/johna",
    "--label",
    "Herdr setup test",
    "--no-focus",
)
workspace = created["workspace"]["workspace_id"]
pane = created["root_pane"]["pane_id"]
try:
    # Build the output marker from separate arguments so terminal command echo
    # cannot satisfy wait-output before the command has actually run.
    call(
        "pane",
        "run",
        pane,
        "sleep 3; printf 'HERDR_%s\\n' PERSISTENCE_OK; "
        'printf \'PI_DIR=%s\\nCLAUDE_DIR=%s\\n\' "$PI_CODING_AGENT_DIR" "$CLAUDE_CONFIG_DIR"; '
        "command -v herdr; type -t wt",
    )
    time.sleep(4)
    call(
        "pane",
        "wait-output",
        pane,
        "--match",
        "HERDR_PERSISTENCE_OK",
        "--timeout",
        "15000",
    )
    text = call(
        "pane", "read", pane, "--source", "recent-unwrapped", "--lines", "40", raw=True
    )
    assert "PI_DIR=/home/johna/.config/pi" in text, text
    assert "CLAUDE_DIR=/home/johna/.config/claude-personal" in text, text
    assert "/home/johna/.local/bin/herdr" in text, text
    assert "function" in text, "Worktrunk shell function missing"
    print(
        "PASS remote process persisted across SSH calls; Nix PATH and personal profile defaults"
    )
    print("PASS Worktrunk integration available without modifying Omarchy shell files")

    call(
        "agent",
        "start",
        "herdr-setup-pi",
        "--kind",
        "pi",
        "--pane",
        pane,
        "--timeout",
        "60000",
    )
    agent = call("agent", "get", "herdr-setup-pi")
    assert agent["agent"]["name"] == "herdr-setup-pi", agent
    assert agent["agent"]["pane_id"] == pane, agent
    assert agent["agent"]["agent"].lower() == "pi", agent
    assert agent["agent"]["interactive_ready"], agent
    print("PASS Pi starts and is detected remotely without a model prompt")
finally:
    call("workspace", "close", workspace)
    print("PASS verification workspace removed; existing workspaces untouched")
