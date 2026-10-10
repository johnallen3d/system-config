#!/usr/bin/env python3
"""Test Headroom's pipe-drain repair and real installed ProxyManager, no model calls.

Run on either host: python3 tests/headroom-proxy.py [--installed]
The installed gate requires the managed repair in both personal/work profiles.
All proxy children use temporary homes and isolated ports, never port 8787.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repair", ROOT / "modules/home-manager/pi/repair-headroom.py")
REPAIR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPAIR)

FAKE = r'''
import http.server
import os
import sys
if "--help" in sys.argv:
    print("headroom proxy")
    raise SystemExit(0)
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/flood":
            # Far larger than a pipe/socket buffer, on each stream independently.
            for fd in (1, 2):
                for _ in range(128):
                    os.write(fd, b"x" * 16384)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ready":true}')
    def log_message(self, *args):
        pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[sys.argv.index("--port") + 1])), Handler).serve_forever()
'''

PROBE = r'''
import assert from 'node:assert/strict';
import { ProxyManager } from './proxy-manager.ts';
const manager = new ProxyManager({port: Number(process.env.TEST_PORT)});
try {
    assert.equal(await manager.healthCheck(), false, 'Test port occupied');
    assert.equal(await manager.ensureRunning(console.log), true);
    assert.equal(manager.isManaged, true);
    if (process.env.EXPECT_DRAIN === 'yes') {
        for (let i = 0; i < 3; i++) {
            const flood = await fetch(`${manager.baseUrl}/flood`, {signal: AbortSignal.timeout(5000)});
            assert.equal(flood.ok, true);
            await flood.text();
            assert.equal(await manager.healthCheck(), true);
        }
        console.log('PASS proxy remains healthy after 12 MiB of stdout/stderr');
    } else {
        await assert.rejects(fetch(`${manager.baseUrl}/flood`, {signal: AbortSignal.timeout(1000)}));
        assert.equal(await manager.healthCheck(), false);
        console.log('PASS reproduced upstream pipe blockage and failed health check');
    }
} finally {
    await manager.stop();
    assert.equal(await manager.healthCheck(), false, 'Child survived shutdown');
}
'''


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.profile = Path(self.tmp.name) / "selected"
        self.package = self.profile / "npm/node_modules/pi-headroom"
        (self.package / "src").mkdir(parents=True)
        self.manifest = self.package / "package.json"
        self.manifest.write_text('{"version":"0.1.0"}')
        self.manager = self.package / "src/proxy-manager.ts"
        self.manager.write_text(REPAIR.OLD)

    def test_idempotent_selected_profile_only(self):
        other = Path(self.tmp.name) / "other/npm/node_modules/pi-headroom/src"
        other.mkdir(parents=True)
        (other / "proxy-manager.ts").write_text(REPAIR.OLD)
        self.assertTrue(REPAIR.repair(self.profile))
        self.assertEqual(self.manager.read_text(), REPAIR.NEW)
        self.assertFalse(REPAIR.repair(self.profile))
        self.assertEqual((other / "proxy-manager.ts").read_text(), REPAIR.OLD)

    def test_reapplied_after_npm_replaces_source(self):
        self.assertTrue(REPAIR.repair(self.profile))
        self.manager.write_text(REPAIR.OLD)
        self.assertTrue(REPAIR.repair(self.profile))
        self.assertEqual(self.manager.read_text(), REPAIR.NEW)

    def test_missing_and_newer_packages_untouched(self):
        self.assertFalse(REPAIR.repair(self.profile / "missing"))
        self.manifest.write_text('{"version":"0.2.0"}')
        self.assertFalse(REPAIR.repair(self.profile))
        self.assertEqual(self.manager.read_text(), REPAIR.OLD)

    def test_known_version_source_drift_fails_without_writing(self):
        self.manager.write_text("changed upstream source")
        with self.assertRaisesRegex(RuntimeError, "target changed"):
            REPAIR.repair(self.profile)
        self.assertEqual(self.manager.read_text(), "changed upstream source")

    def test_launcher_repairs_after_bootstrap_before_extension_load(self):
        launcher = (ROOT / "modules/home-manager/packages/pi.nix").read_text()
        self.assertLess(launcher.index('marker="$PI_CODING_AGENT_DIR/packages-installed"'), launcher.index('${repairHeadroom} || exit $?'))
        self.assertLess(launcher.index('${repairHeadroom} || exit $?'), launcher.index('exec ${runPi}'))


def lifecycle(source: str, drain: bool):
    # Resolve through mise before changing HOME; shims need the real trust state.
    node = subprocess.run([shutil.which("node"), "--print", "process.execPath"], capture_output=True, text=True, check=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="headroom-pipes-") as tmp:
        root = Path(tmp)
        executable = root / ".pi/headroom-venv/bin/headroom"
        executable.parent.mkdir(parents=True)
        executable.write_text(f"#!{sys.executable}\n" + FAKE)
        executable.chmod(0o700)
        (root / "proxy-manager.ts").write_text(source)
        (root / "probe.mjs").write_text(PROBE)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = dict(os.environ, HOME=tmp, TEST_PORT=str(port), EXPECT_DRAIN="yes" if drain else "no")
        # Do not use any globally installed headroom; only this fake venv CLI.
        env["PATH"] = str(Path(node).parent)
        subprocess.run([node, "--experimental-strip-types", str(root / "probe.mjs")], env=env, check=True, timeout=45)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(RepairTests))
    assert result.wasSuccessful()
    for name in ["pi", "pi-work"] if args.installed else ["pi"]:
        profile = Path.home() / ".config" / name if args.installed else Path(os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".config/pi"))
        package = profile / "npm/node_modules/pi-headroom"
        assert json.loads((package / "package.json").read_text())["version"] == "0.1.0", "Review regression probe for new upstream version"
        source = (package / "src/proxy-manager.ts").read_text()
        if args.installed:
            assert REPAIR.NEW in source, f"Managed repair missing: {profile}"
        upstream = source.replace(REPAIR.NEW, REPAIR.OLD)
        assert upstream.count(REPAIR.OLD) == 1
        lifecycle(upstream, False)
        lifecycle(upstream.replace(REPAIR.OLD, REPAIR.NEW), True)
        print(f"PASS {profile}: installed manager baseline reproduction and repaired lifecycle", flush=True)


if __name__ == "__main__":
    main()
