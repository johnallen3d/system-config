#!/usr/bin/env python3
"""Verify managed Pi launchers start real Headroom and compress synthetic context.

Run on Mac or Omarchy: python3 tests/headroom-live.py
Uses both profiles, isolated ports and no model/provider calls or agent restarts.
"""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

PROBE = r'''
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { ProxyManager } from './proxy-manager.ts';
const profile = process.env.PI_CODING_AGENT_DIR;
assert.equal(profile, process.env.EXPECTED_PROFILE);
const { HeadroomClient, compress } = await import(pathToFileURL(`${profile}/npm/node_modules/headroom-ai/dist/index.js`).href);
const manager = new ProxyManager({port: Number(process.env.TEST_PORT)});
assert.equal(await manager.healthCheck(), false, 'Test port already occupied');
try {
    assert.equal(await manager.ensureRunning(console.log), true);
    const health = await (await fetch(`${manager.baseUrl}/health`)).json();
    assert.equal(health.ready, true);
    assert.equal(health.rust_core, 'loaded');
    const messages = [{role: 'user', content: 'Summarize the service logs.'}];
    for (let i = 0; i < 8; i++) {
        messages.push({role: 'assistant', content: null, tool_calls: [{id: `logs${i}`, type: 'function', function: {name: 'read_logs', arguments: '{}'}}]});
        messages.push({role: 'tool', tool_call_id: `logs${i}`, content: JSON.stringify(Array.from({length: 300}, (_, j) => ({timestamp: `2026-10-10T10:${String(j % 60).padStart(2, '0')}:00Z`, level: 'INFO', service: 'test-service', message: 'Request completed successfully', status: 200, request_id: `synthetic-${i}-${j}`})))});
    }
    messages.push({role: 'user', content: 'What happened?'});
    const result = await compress(messages, {client: new HeadroomClient({baseUrl: manager.baseUrl, fallback: false, timeout: 60000}), model: 'gpt-4o', fallback: false});
    assert.equal(result.compressed, true, JSON.stringify(result));
    assert.ok(result.tokensSaved > 0, JSON.stringify(result));
    assert.equal(await manager.healthCheck(), true);
    console.log(JSON.stringify({profile, ready: health.ready, rust: health.rust_core, tokensSaved: result.tokensSaved, transforms: result.transformsApplied}));
} finally {
    await manager.stop();
    assert.equal(await manager.healthCheck(), false, 'Test proxy survived shutdown');
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-port", type=int, default=19787, help="First test port; refuses an occupied port")
    args = parser.parse_args()
    home = Path.home()
    candidates = [home / ".local/bin/pi", home / ".nix-profile/bin/pi", Path(f"/etc/profiles/per-user/{home.name}/bin/pi"), Path("/run/current-system/sw/bin/pi")]
    wrapper = next(path for path in candidates if path.exists())
    source = wrapper.read_text()
    lines = source.splitlines()
    indexes = [i for i, line in enumerate(lines) if line.lstrip().startswith("exec ")]
    assert len(indexes) == 1, f"Review managed launcher shape: {wrapper}"
    node = subprocess.run([shutil.which("node"), "--print", "process.execPath"], capture_output=True, text=True, check=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="headroom-live-") as tmp:
        directory = Path(tmp)
        probe = directory / "probe.mjs"
        probe.write_text(PROBE)
        lines[indexes[0]] = f"exec {shlex.quote(node)} --experimental-strip-types {shlex.quote(str(probe))}"
        launcher = directory / "pi"
        launcher.write_text("\n".join(lines) + "\n")
        for index, name in enumerate(["pi", "pi-work"]):
            profile = home / ".config" / name
            env = dict(os.environ, PI_CODING_AGENT_DIR=str(profile), EXPECTED_PROFILE=str(profile), TEST_PORT=str(args.base_port + index), HEADROOM_BEACON="off")
            for variable in ["CLAUDE_CONFIG_DIR", "LD_LIBRARY_PATH", "HEADROOM_URL", "HEADROOM_PORT"]:
                env.pop(variable, None)
            manager = profile / "npm/node_modules/pi-headroom/src/proxy-manager.ts"
            (directory / "proxy-manager.ts").write_bytes(manager.read_bytes())
            subprocess.run(["bash", str(launcher)], env=env, check=True, timeout=120)
            print(f"PASS {profile}: managed launcher, proxy health/native core, real context compression and shutdown", flush=True)


if __name__ == "__main__":
    main()
