#!/usr/bin/env python3
"""Offline harness orchestration/profile/failure tests; no network or model calls."""

import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / ".mise/tasks/harness-refresh"
UPDATE = ROOT / ".mise/tasks/update-system"


class HarnessRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.log = self.home / "calls.jsonl"
        self.env = dict(os.environ, HOME=str(self.home), USER="test",
                        PATH=f"{self.bin}:{os.environ['PATH']}",
                        TEST_LOG=str(self.log), MOCK_PLATFORM="Darwin",
                        PI_CODING_AGENT_DIR="/inherited/do-not-use",
                        CLAUDE_CONFIG_DIR="/inherited/do-not-use")
        for key in list(self.env):
            if key.startswith("usage_"):
                del self.env[key]
        # Match pi-refresh's preferred Nix tool directory, keeping Python out of
        # real mise shims when HOME is an isolated fixture.
        nix_bin = self.home / '.nix-profile/bin'
        for tool in ('node', 'npm'):
            self.executable(nix_bin / tool, '#!/bin/bash\nexit 0\n')
        (nix_bin / 'python3').symlink_to(sys.executable)
        self.executable(self.bin / "uname", '#!/bin/bash\necho "$MOCK_PLATFORM"\n')
        self.executable(self.bin / "mise", '''#!/usr/bin/env python3
import json, os, subprocess, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['mise', sys.argv[1:]]) + '\\n')
if '--' in sys.argv:
    env = dict(os.environ, PI_CODING_AGENT_DIR=os.environ['HOME']+'/.config/pi-work',
               CLAUDE_CONFIG_DIR=os.environ['HOME']+'/.config/claude-gmatter')
    sys.exit(subprocess.call(sys.argv[sys.argv.index('--')+1:], env=env))
sys.exit(int(os.environ.get('MOCK_REBUILD_RC', '0')))
''')
        self.executable(self.bin / "ssh", '''#!/usr/bin/env python3
import json, os, pathlib, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['ssh', sys.argv[1:]]) + '\\n')
pathlib.Path(os.environ['HOME'], 'payload.sh').write_text(sys.stdin.read())
sys.exit(int(os.environ.get('MOCK_SSH_RC', '0')))
''')
        self.executable(self.bin / "pi", '''#!/usr/bin/env python3
import json, os, sys
profile = os.environ['PI_CODING_AGENT_DIR']
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['pi', profile, sys.argv[1:]]) + '\\n')
sys.exit(int(os.environ.get('MOCK_PI_RC', '0'))
         if sys.argv[1] == 'update' else 0)
''')
        self.executable(self.home / ".local/bin/claude", '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['claude', os.environ['CLAUDE_CONFIG_DIR'], sys.argv[1:]]) + '\\n')
key = 'MOCK_MARKETPLACE_RC' if 'marketplace' in sys.argv else 'MOCK_PLUGIN_RC'
sys.exit(int(os.environ.get(key, '0')))
''')
        for profile in ("pi", "pi-work", "pi-notes"):
            directory = self.home / ".config" / profile
            directory.mkdir(parents=True)
            (directory / "packages-installed").write_text("test")
            (directory / "settings.json").write_text(json.dumps({"packages": [
                "npm:test-package", "git:github.com/example/test-kit"]}))

    @staticmethod
    def executable(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Do not let a mise python shim rewrite PATH and bypass the mock tools.
        content = content.replace('#!/usr/bin/env python3', f'#!{sys.executable}')
        path.write_text(content)
        path.chmod(0o755)

    def run_task(self, *args, script=TASK, **env):
        return subprocess.run(["bash", str(script), *args],
                              env=dict(self.env, **env), capture_output=True,
                              text=True, timeout=30)

    def calls(self, kind):
        if not self.log.exists():
            return []
        return [entry for line in self.log.read_text().splitlines()
                if (entry := json.loads(line))[0] == kind]

    def test_mac_refreshes_all_profiles_and_ships_only_workers(self):
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('[Darwin] SUCCESS', result.stdout)
        self.assertIn('[Omarchy] SUCCESS', result.stdout)
        expected = {str(self.home / '.config' / profile)
                    for profile in ('pi', 'pi-work', 'pi-notes')}
        for command in ('install', 'update'):
            self.assertEqual({c[1] for c in self.calls('pi') if c[2][0] == command}, expected)
        self.assertEqual([c[2] for c in self.calls('claude')], [
            ['plugin', 'marketplace', 'update', 'amfaro'],
            ['plugin', 'update', 'agent-kit@amfaro']])
        self.assertTrue(all(c[1] == str(self.home / '.config/claude-gmatter')
                            for c in self.calls('claude')))
        self.assertEqual(self.calls('mise')[0][1][:4],
                         ['-C', str(self.home / 'dev/src/amfaro'), 'exec', '--'])
        self.assertEqual(len(self.calls('ssh')), 1)
        self.assertEqual(self.calls('ssh')[0][1][-2:], ['johna@omarchy', 'bash -s'])
        payload = (self.home / 'payload.sh').read_text()
        encoded = payload.split("<<'HARNESS_PAYLOAD' | tar -xzf - -C \"$tmp_dir\"\n")[1].split('\nHARNESS_PAYLOAD')[0]
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(encoded)), mode='r:gz') as archive:
            self.assertEqual(set(archive.getnames()), {'harness-refresh-local', 'pi-refresh'})
            for name in archive.getnames():
                self.assertEqual(archive.extractfile(name).read(),
                                 (ROOT / '.mise/scripts' / name).read_bytes())
        self.assertIn('mise -C "$HOME/dev/src/amfaro" exec -- bash "$tmp_dir/harness-refresh-local"', payload)
        self.assertIn("trap 'rm -rf \"$tmp_dir\"' EXIT", payload)

    def test_retired_personal_packages_are_bounded_and_profile_local(self):
        personal = self.home / '.config/pi'
        (personal / 'npm').mkdir()
        manifest = personal / 'npm/package.json'
        manifest.write_text(json.dumps({'dependencies': {
            'pi-mcp-adapter': '^5.1.0', 'context-mode': '^1.0.0',
            '@tmustier/pi-skill-creator': '^0.3.0', 'unrelated-user-package': '^1.0.0'}}))
        settings = json.loads((personal / 'settings.json').read_text())
        settings['packages'].append({'source': 'npm:@tmustier/pi-skill-creator@0.3.0'})
        (personal / 'settings.json').write_text(json.dumps(settings))
        (personal / 'auth.json').write_text('credential sentinel')
        self.executable(self.home / '.nix-profile/bin/npm', '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['npm', os.environ['PI_CODING_AGENT_DIR'], sys.argv[1:]]) + '\\n')
''')
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('npm'), [['npm', str(personal), [
            'uninstall', '--prefix', str(personal / 'npm'), '--legacy-peer-deps',
            'context-mode', 'pi-mcp-adapter']]])
        self.assertEqual((personal / 'auth.json').read_text(), 'credential sentinel')

    def test_retirement_failure_is_reported_but_other_profiles_continue(self):
        personal = self.home / '.config/pi'
        (personal / 'npm').mkdir()
        (personal / 'npm/package.json').write_text(json.dumps({'dependencies': {'pi-mcp-adapter': '^5.1.0'}}))
        self.executable(self.home / '.nix-profile/bin/npm', '#!/bin/bash\nexit 1\n')
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 1)
        updated = {c[1] for c in self.calls('pi') if c[2][0] == 'update'}
        self.assertEqual(updated, {str(self.home / '.config/pi-work'), str(self.home / '.config/pi-notes')})

    def test_local_only_direct_and_mise_flag(self):
        for args, env in ((['--local-only'], {}), ([], {'usage_local_only': 'true'})):
            result = self.run_task(*args, **env)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('ssh'), [])

    def test_linux_never_calls_ssh(self):
        result = self.run_task(MOCK_PLATFORM='Linux')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('ssh'), [])

    def test_remote_failure_is_not_success(self):
        result = self.run_task(MOCK_SSH_RC='255')
        self.assertEqual(result.returncode, 1)
        self.assertIn('[Darwin] SUCCESS', result.stdout)
        self.assertIn('shared refresh is partial', result.stderr)
        self.assertNotIn('All requested hosts refreshed', result.stdout)

    def test_pi_failure_still_attempts_claude_and_remote(self):
        result = self.run_task(MOCK_PI_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls('claude')), 2)
        self.assertEqual(len(self.calls('ssh')), 1)
        self.assertEqual(len([c for c in self.calls('pi') if c[2][0] == 'update']), 3)
        self.assertIn('[Darwin] FAILED', result.stderr)
        self.assertIn('[Omarchy] SUCCESS', result.stdout)

    def test_marketplace_failure_skips_plugin_but_not_remote(self):
        result = self.run_task(MOCK_MARKETPLACE_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls('claude')), 1)
        self.assertEqual(len(self.calls('ssh')), 1)

    def test_plugin_failure_still_attempts_remote(self):
        result = self.run_task(MOCK_PLUGIN_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls('ssh')), 1)

    def test_missing_claude_is_failure(self):
        (self.home / '.local/bin/claude').unlink()
        result = self.run_task()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.calls('ssh')), 1)

    def test_unknown_argument_has_no_side_effects(self):
        result = self.run_task('--wrong')
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.log.exists())

    def test_update_system_harness_only_has_no_rebuild_even_on_linux(self):
        result = self.run_task(script=UPDATE, usage_harness_only='true', MOCK_PLATFORM='Linux')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('mise'), [['mise', ['run', 'harness-refresh']]])

    def test_update_system_rejects_linux_rebuild(self):
        result = self.run_task(script=UPDATE, MOCK_PLATFORM='Linux')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls('mise'), [])

    def test_update_system_refresh_after_successful_mac_rebuild(self):
        result = self.run_task(script=UPDATE, usage_switch_only='true', usage_harness_refresh='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('mise'), [
            ['mise', ['run', 'nix-rebuild', '--switch-only']],
            ['mise', ['run', 'harness-refresh']]])

    def test_update_system_failed_rebuild_does_not_refresh(self):
        result = self.run_task(script=UPDATE, usage_harness_refresh='true', MOCK_REBUILD_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls('mise'), [['mise', ['run', 'nix-rebuild']]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
