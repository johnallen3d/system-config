#!/usr/bin/env python3
"""Check the installed work kit without model calls or account credentials.

Run on Omarchy after provisioning: python3 tests/agent-work-kit.py
"""

import json
from pathlib import Path
import subprocess


def main():
    home = Path.home()
    node = home / ".nix-profile/bin/node"
    checkout = home / ".config/pi-work/git/github.com/amfaro/agent-kit"
    assert (checkout / "package.json").is_file(), "Work Pi package not installed"
    subprocess.run(
        [str(node), "-e", """
const sharp = require('sharp');
sharp({create:{width:1,height:1,channels:3,background:'#000'}}).png().toBuffer()
  .then(bytes => { if (!bytes.length) process.exit(1); console.log('PASS Sharp native image processing'); })
  .catch(error => { console.error(error.message); process.exit(1); });
"""], cwd=checkout, check=True, timeout=30,
    )

    result = subprocess.run(
        ["mise", "-C", str(home / "dev/src/amfaro"), "exec", "--",
         str(home / ".local/bin/claude"), "plugin", "list", "--json"],
        check=True, capture_output=True, text=True, timeout=30,
    )
    plugin = next(item for item in json.loads(result.stdout) if item["id"] == "agent-kit@amfaro")
    assert plugin["enabled"]
    print(f"PASS work Claude plugin enabled: {plugin['version']}")

    # The Claude adapter is dependency-free by design. Test its real stdio
    # startup/handshake despite Claude's advisory about bundled Pi dependencies.
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "system-config-smoke", "version": "1"},
        }},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    result = subprocess.run(
        [str(node), str(Path(plugin["installPath"]) / "claude-code/mcp-server.ts")],
        input="".join(json.dumps(request) + "\n" for request in requests),
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    replies = {reply["id"]: reply for line in result.stdout.splitlines()
               if (reply := json.loads(line)).get("id") is not None}
    assert "result" in replies[1], replies[1]
    tools = {tool["name"] for tool in replies[2]["result"]["tools"]}
    assert {"find_tools", "call_tool"} <= tools, tools
    print("PASS work Claude MCP startup, initialize, and tools/list")


if __name__ == "__main__":
    main()
