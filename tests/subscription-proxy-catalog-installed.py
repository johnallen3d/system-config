#!/usr/bin/env python3
"""Read-only installed catalog/scheduler checks; no tokens printed or model calls."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

HOME = Path.home()
ROOT = HOME / ".config/subscription-proxy"
source = Path(__file__).resolve().parents[1] / "modules/home-manager/subscription-proxy"
sys.path.insert(0, str(source))
import go_catalog

cache = json.loads((ROOT / "go-catalog.json").read_text())
expected = go_catalog.build_catalog(cache["provider"], cache["available"])
known = {e["id"]: e for e in expected["models"]}
entries = cache["catalog"]["models"]
assert len(entries) > 3
assert all(known[e["id"]] == e for e in entries)
go = json.loads((HOME / ".config/pi-work/models.json").read_text())["providers"]["subscription-go"]
assert go["models"] == [e["pi"] for e in entries]
assert go["baseUrl"] == "http://100.97.112.40:8318/v1"
assert go["apiKey"].startswith("!") and "client-key work" in go["apiKey"]
assert go["api"] == "openai-completions"
assert go["compat"]["sendSessionAffinityHeaders"] and go["compat"]["sessionAffinityFormat"] == "openai"
assert "claude" not in json.dumps(go).lower()
print(f"PASS installed Go catalog: {len(entries)} validated non-Claude models, upstream capabilities, stable proxy key/session routing")

if sys.platform == "darwin":
    label = "org.nix-community.home.subscription-proxy-catalog"
    files = list((HOME / "Library/LaunchAgents").glob("*subscription-proxy-catalog*.plist"))
    assert len(files) == 1, files
    config = plistlib.loads(files[0].read_bytes())
    assert config["Label"] == label
    assert config["StartInterval"] == 86400 and config["RunAtLoad"]
    assert "--server" not in config["ProgramArguments"]
    assert config["EnvironmentVariables"]["PI_CODING_AGENT_DIR"] == str(HOME / ".config/pi-work")
    assert config["EnvironmentVariables"]["CLAUDE_CONFIG_DIR"] == str(HOME / ".config/claude-gmatter")
    state = subprocess.check_output(["launchctl", "print", f"gui/{os.getuid()}/{label}"], text=True)
    assert "last exit code = 0" in state, "Scheduled refresh has not completed successfully"
    print("PASS loaded Mac launch agent: daily + login refresh, explicit paired work profiles, successful last scheduled run")
else:
    timer = "subscription-proxy-catalog.timer"
    assert subprocess.check_output(["systemctl", "--user", "is-enabled", timer], text=True).strip() == "enabled"
    assert subprocess.check_output(["systemctl", "--user", "is-active", timer], text=True).strip() == "active"
    unit = subprocess.check_output(["systemctl", "--user", "cat", "subscription-proxy-catalog.service"], text=True)
    assert "--server" in unit
    assert f"PI_CODING_AGENT_DIR={HOME}/.config/pi-work" in unit
    assert f"CLAUDE_CONFIG_DIR={HOME}/.config/claude-gmatter" in unit
    timer_unit = subprocess.check_output(["systemctl", "--user", "cat", timer], text=True)
    assert "OnCalendar=" in timer_unit and "Persistent=true" in timer_unit
    result = subprocess.check_output(["systemctl", "--user", "show", "subscription-proxy-catalog.service", "-p", "Result", "-p", "ExecMainStatus"], text=True)
    assert "Result=success" in result and "ExecMainStatus=0" in result
    print("PASS enabled/active Omarchy daily catch-up timer, explicit paired work profiles, successful last service run")
