#!/usr/bin/env python3
"""Check installed Omarchy Pi library wiring and Headroom's real proxy lifecycle.

Uses temporary launcher copies, isolated ports, and no agent/model calls.
Run on Omarchy: python3 tests/headroom-omarchy.py
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile


PROBE = """
import assert from 'node:assert/strict';
const profile = process.env.PI_CODING_AGENT_DIR;
const { ProxyManager } = await import('./proxy-manager.ts');
assert.equal(profile, process.env.EXPECTED_PI_PROFILE);
assert.equal(process.env.CLAUDE_CONFIG_DIR, process.env.EXPECTED_CLAUDE_PROFILE);
const manager = new ProxyManager({ port: Number(process.env.TEST_HEADROOM_PORT) });
// Never attach to or stop a proxy belonging to an active agent.
assert.equal(await manager.healthCheck(), false, 'Test port is already occupied');
try {
  assert.equal(await manager.ensureRunning(console.log), true);
  assert.equal(manager.isManaged, true);
  const health = await (await fetch(`${manager.baseUrl}/health`)).json();
  assert.equal(health.ready, true);
  assert.equal(health.rust_core, 'loaded');
  console.log(JSON.stringify({ profile, ready: health.ready, rust: health.rust_core }));
} finally {
  await manager.stop();
}
assert.equal(await manager.healthCheck(), false, 'Test proxy was not stopped');
"""


def launcher(source, command):
    lines = source.splitlines()
    indexes = [i for i, line in enumerate(lines) if line.startswith("exec ")]
    assert len(indexes) == 1
    lines[indexes[0]] = command
    return "\n".join(lines) + "\n"


def main():
    home = Path.home()
    source = (home / ".local/bin/pi").read_text()
    assert 'export LD_LIBRARY_PATH="/nix/store/' in source
    assert '${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}' in source
    assert "LD_LIBRARY_PATH" not in (home / ".local/bin/claude").read_text()
    with tempfile.TemporaryDirectory(prefix="headroom-omarchy-") as tmp:
        directory = Path(tmp)
        probe = directory / "proxy.mjs"
        probe.write_text(PROBE)
        script = directory / "pi"
        script.write_text(launcher(source, f'exec node --experimental-strip-types "{probe}"'))
        for index, (pi_name, claude_name) in enumerate((
            ("pi", "claude-personal"), ("pi-work", "claude-gmatter"),
        )):
            profile = str(home / ".config" / pi_name)
            claude = str(home / ".config" / claude_name)
            env = dict(os.environ, PI_CODING_AGENT_DIR=profile,
                       EXPECTED_PI_PROFILE=profile, EXPECTED_CLAUDE_PROFILE=claude,
                       TEST_HEADROOM_PORT=str(18787 + index),
                       HEADROOM_BEACON="off")
            env.pop("CLAUDE_CONFIG_DIR", None)
            env.pop("LD_LIBRARY_PATH", None)
            # Node refuses type stripping inside node_modules. Copy the exact
            # installed standalone manager into the temporary test directory.
            manager = Path(profile) / "npm/node_modules/pi-headroom/src/proxy-manager.ts"
            (directory / "proxy-manager.ts").write_bytes(manager.read_bytes())
            subprocess.run(["bash", str(script)], env=env, check=True, timeout=90)
            print(f"PASS {pi_name}: extension auto-start, native core, health, shutdown; profile preserved")

        # Preserve existing library paths, without setting them for the shell.
        script.write_text(launcher(source, 'printf "%s\\n" "$LD_LIBRARY_PATH"'))
        env = dict(os.environ, LD_LIBRARY_PATH="/sentinel")
        result = subprocess.run(["bash", str(script)], env=env, check=True,
                                capture_output=True, text=True)
        paths = result.stdout.strip().split(":")
        assert len(paths) == 3 and paths[-1] == "/sentinel", json.dumps(paths)
        assert all(path.startswith("/nix/store/") for path in paths[:2])
        print("PASS Pi-only Nix runtime paths; inherited library paths preserved; Claude unchanged")


if __name__ == "__main__":
    main()
