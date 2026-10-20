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
                        XDG_STATE_HOME=str(self.home / '.local/state'),
                        PATH=f"{self.bin}:{os.environ['PATH']}",
                        TEST_LOG=str(self.log), MOCK_PLATFORM="Darwin",
                        PI_CODING_AGENT_DIR="/inherited/do-not-use",
                        CLAUDE_CONFIG_DIR="/inherited/do-not-use",
                        SYSTEM_CONFIG_COORDINATED=str(ROOT),
                        SYSTEM_CONFIG_TASK_ROOT=str(ROOT), SYSTEM_CONFIG_TOOL_ROOT=str(ROOT))
        for key in list(self.env):
            if key.startswith("usage_"):
                del self.env[key]
        # Match pi-refresh's preferred Nix tool directory, keeping Python out of
        # real mise shims when HOME is an isolated fixture.
        nix_bin = self.home / '.nix-profile/bin'
        self.executable(nix_bin / 'node', '#!/bin/bash\nexit 0\n')
        self.executable(nix_bin / 'npm', '''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['npm', os.environ['PI_CODING_AGENT_DIR'], sys.argv[1:], os.getcwd()]) + '\\n')
if sys.argv[1] == 'audit':
    print(os.environ.get('MOCK_AUDIT_JSON', json.dumps({'metadata': {'vulnerabilities': {'total': 0}}})))
    sys.exit(int(os.environ.get('MOCK_AUDIT_RC', '0')))
if sys.argv[1] == 'install-scripts':
    print(os.environ.get('MOCK_SCRIPTS_JSON', '{"allowScripts": []}'))
    sys.exit(int(os.environ.get('MOCK_SCRIPTS_RC', '0')))
sys.exit(int(os.environ.get('MOCK_DEPENDENCY_RC', '0')))
''')
        # Deployment orchestration is tested separately. Never let these
        # harness-only fixtures access a real coordinator, Nix, or mise config.
        self.executable(nix_bin / 'python3', '''#!/usr/bin/env python3
import os, pathlib, sys
if len(sys.argv) > 2 and sys.argv[1].endswith('/deployment_state.py'):
    if sys.argv[2] == 'plan':
        pathlib.Path(sys.argv[4]).write_text(sys.argv[3])
    elif sys.argv[2] != 'finish':
        raise SystemExit('Unexpected coordinator invocation')
    raise SystemExit(0)
os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
''')
        (self.bin / 'python3').symlink_to(nix_bin / 'python3')
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
import json, os, shutil, sys
from pathlib import Path
profile = os.environ['PI_CODING_AGENT_DIR']
if os.environ.get('MOCK_PI_OUTPUT'):
    print(os.environ['MOCK_PI_OUTPUT'])
with open(os.environ['TEST_LOG'], 'a') as log:
    log.write(json.dumps(['pi', profile, sys.argv[1:]]) + '\\n')
if sys.argv[1:2] == ['update'] and sys.argv[2].startswith('git:') and os.environ.get('TEST_GIT_FIXTURE'):
    target = Path(profile) / 'git' / sys.argv[2][4:].split('@')[0].removesuffix('.git')
    shutil.copytree(os.environ['TEST_GIT_FIXTURE'], target, dirs_exist_ok=True)
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
        self.assertEqual({c[1] for c in self.calls('pi') if c[2][0] == 'update'}, expected)
        self.assertEqual([c for c in self.calls('pi') if c[2][0] == 'install'], [])
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
            self.assertEqual(set(archive.getnames()), {'harness-refresh-local', 'pi-refresh', 'harness-report.py'})
            for name in archive.getnames():
                self.assertEqual(archive.extractfile(name).read(),
                                 (ROOT / '.mise/scripts' / name).read_bytes())
        self.assertIn('mise -C "$HOME/dev/src/amfaro" exec -- bash "$tmp_dir/harness-refresh-local"', payload)
        self.assertIn("trap 'rm -rf \"$tmp_dir\"' EXIT", payload)

    def test_retired_personal_packages_are_bounded_and_profile_local(self):
        personal = self.home / '.config/pi'
        (personal / 'npm').mkdir()
        (personal / 'npm/package-lock.json').write_text(json.dumps({'packages': {}}))
        manifest = personal / 'npm/package.json'
        manifest.write_text(json.dumps({'dependencies': {
            'pi-mcp-adapter': '^5.1.0', 'context-mode': '^1.0.0',
            '@tmustier/pi-skill-creator': '^0.3.0', 'unrelated-user-package': '^1.0.0'}}))
        settings = json.loads((personal / 'settings.json').read_text())
        settings['packages'].append({'source': 'npm:@tmustier/pi-skill-creator@0.3.0'})
        (personal / 'settings.json').write_text(json.dumps(settings))
        (personal / 'auth.json').write_text('credential sentinel')
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call[:3] for call in self.calls('npm') if call[2][0] == 'uninstall'], [
            ['npm', str(personal), ['uninstall', '--prefix', str(personal / 'npm'),
                                   '--legacy-peer-deps', 'context-mode', 'pi-mcp-adapter']]])
        self.assertEqual((personal / 'auth.json').read_text(), 'credential sentinel')

    def dependency_root(self, root):
        root.mkdir(parents=True, exist_ok=True)
        manifest = {'dependencies': {'test-package': '^1.0.0'},
                    'devDependencies': {'test-dev': '^1.0.0'},
                    'peerDependencies': {'test-peer': '*'},
                    'optionalDependencies': {'test-optional': '^1.0.0'}}
        (root / 'package.json').write_text(json.dumps(manifest))
        packages = {
            '': manifest,
            'node_modules/test-package': {'version': '1.0.0'},
            'node_modules/test-package/node_modules/brace-expansion': {'version': '5.0.7'},
            'node_modules/@example/transitive': {'version': '1.0.0'},
            'node_modules/test-dev': {'version': '1.0.0', 'dev': True},
            'node_modules/dev-only-child': {'version': '1.0.0', 'dev': True},
            'node_modules/test-peer': {'version': '1.0.0'},
            'node_modules/host-provided-peer': {'version': '1.0.0', 'peer': True},
            'node_modules/test-optional': {'version': '1.0.0'},
            'node_modules/optional-child': {'version': '1.0.0', 'optional': True},
            'node_modules/local-link': {'link': True},
        }
        (root / 'package-lock.json').write_text(json.dumps({'lockfileVersion': 3, 'packages': packages}))
        return (root / 'package.json').read_bytes()

    def test_transitive_refresh_is_bounded_and_profile_local(self):
        roots = []
        for name in ('pi', 'pi-work', 'pi-notes'):
            profile = self.home / '.config' / name
            settings = {'packages': [{'source': 'npm:test-package@1.0.0'},
                                     {'source': 'git:github.com/example/test-kit'}]}
            (profile / 'settings.json').write_text(json.dumps(settings))
            for suffix in ('npm', 'git/github.com/example/test-kit'):
                root = profile / suffix
                roots.append((profile, root, self.dependency_root(root)))
            self.dependency_root(profile / 'git/github.com/example/undeclared-cache')
            (profile / 'auth.json').write_text('credential sentinel')
        fixture = self.bin / 'git-dependency-fixture'
        self.dependency_root(fixture)
        result = self.run_task('--local-only', TEST_GIT_FIXTURE=str(fixture))
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = {call[3]: call for call in self.calls('npm') if call[2][0] == 'update'}
        self.assertEqual(len(calls), 6)
        for profile, root, manifest in roots:
            call = calls[str(root.resolve())]
            self.assertEqual(call[1], str(profile))
            self.assertEqual(call[3], str(root.resolve()))
            self.assertEqual(call[2], ['update', '--save=false', '--omit=dev',
                                     '--legacy-peer-deps', '--no-fund',
                                     '@example/transitive', 'brace-expansion', 'optional-child'])
            self.assertEqual((root / 'package.json').read_bytes(), manifest)
            self.assertEqual((profile / 'auth.json').read_text(), 'credential sentinel')
        self.assertEqual(len([c for c in self.calls('pi') if c[2] == ['update', 'npm:test-package@1.0.0']]), 3)
        for command in ('audit', 'install-scripts'):
            reports = [c for c in self.calls('npm') if c[2][0] == command]
            self.assertEqual(len(reports), 6)
            self.assertEqual({c[3] for c in reports}, {str(root.resolve()) for _, root, _ in roots})
            for call in reports:
                self.assertTrue(Path(call[3]).is_relative_to(Path(call[1]).resolve()))

    def test_dependency_failure_propagates_and_other_profiles_continue(self):
        for name in ('pi', 'pi-work', 'pi-notes'):
            self.dependency_root(self.home / '.config' / name / 'npm')
        result = self.run_task(MOCK_DEPENDENCY_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len([c for c in self.calls('npm') if c[2][0] == 'update']), 3)
        self.assertEqual(len(self.calls('claude')), 2)
        self.assertEqual(len(self.calls('ssh')), 1)
        for label in ('personal', 'work', 'notes'):
            self.assertIn(f'{label}:npm-dependencies', result.stderr)

    def test_missing_lock_fails_without_unbounded_fallback(self):
        root = self.home / '.config/pi/npm'
        self.dependency_root(root)
        (root / 'package-lock.json').unlink()
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls('npm'), [])
        self.assertIn('[personal] FAILED; log:', result.stdout)
        log = next((self.home / '.local/state/system-config/harness-refresh').glob('*/personal.log'))
        self.assertIn('Cannot read dependency lock', log.read_text())
        self.assertEqual(len([c for c in self.calls('pi') if c[2] == ['update', 'npm:test-package']]), 3)

    def test_failed_reconciliation_skips_dependency_refresh(self):
        for name in ('pi', 'pi-work', 'pi-notes'):
            self.dependency_root(self.home / '.config' / name / 'npm')
        result = self.run_task('--local-only', MOCK_PI_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls('npm'), [])

    def test_retirement_failure_is_reported_but_other_profiles_continue(self):
        personal = self.home / '.config/pi'
        (personal / 'npm').mkdir()
        (personal / 'npm/package.json').write_text(json.dumps({'dependencies': {'pi-mcp-adapter': '^5.1.0'}}))
        self.executable(self.home / '.nix-profile/bin/npm', '#!/bin/bash\nexit 1\n')
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 1)
        updated = {c[1] for c in self.calls('pi') if c[2][0] == 'update'}
        self.assertEqual(updated, {str(self.home / '.config/pi-work'), str(self.home / '.config/pi-notes')})

    def test_notes_retirement_preserves_declarations_references_and_other_profiles(self):
        for name in ('pi-work', 'pi-notes'):
            profile = self.home / '.config' / name
            self.dependency_root(profile / 'npm')
            (profile / 'npm/package.json').write_text(json.dumps({'dependencies': {
                'pi-mcp-adapter': '^2.21.1', 'pi-claude-bridge': '^0.6.3',
                'pi-headroom': '^0.1.0', 'unrelated-user-package': '^1.0.0'}}))
            (profile / 'auth.json').write_text('credential sentinel')
        notes = self.home / '.config/pi-notes'
        settings = {'packages': ['git:github.com/badlogic/pi-telegram', 'npm:pi-headroom'],
                    'extensions': ['./npm/node_modules/pi-claude-bridge/extension.ts']}
        (notes / 'settings.json').write_text(json.dumps(settings))
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        removed = [c for c in self.calls('npm') if c[2][0] == 'uninstall']
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0][1], str(notes))
        self.assertEqual(removed[0][2], ['uninstall', '--prefix', str(notes / 'npm'),
                                        '--legacy-peer-deps', 'pi-mcp-adapter'])
        self.assertEqual((notes / 'auth.json').read_text(), 'credential sentinel')

    def test_profile_script_decisions_are_pinned_and_preserve_user_policy(self):
        root = self.home / '.config/pi-work/npm'
        self.dependency_root(root)
        manifest = json.loads((root / 'package.json').read_text())
        manifest['allowScripts'] = {'esbuild@0.28.2': False, 'user-package': True}
        (root / 'package.json').write_text(json.dumps(manifest))
        lock = json.loads((root / 'package-lock.json').read_text())
        for name, version in (('esbuild', '0.28.2'), ('fsevents', '2.3.3')):
            lock['packages']['node_modules/' + name] = {
                'version': version, 'resolved': f'https://registry.npmjs.org/{name}/-/{name}-{version}.tgz'}
        (root / 'package-lock.json').write_text(json.dumps(lock))
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        policy = json.loads((root / 'package.json').read_text())['allowScripts']
        self.assertEqual(policy, {'esbuild@0.28.2': False, 'fsevents@2.3.3': False, 'user-package': True})

    def test_profile_policy_preserves_name_only_and_disjunction_decisions(self):
        import runpy
        helper = runpy.run_path(str(ROOT / '.mise/scripts/harness-report.py'))
        root = self.home / '.config/pi-work/npm'
        self.dependency_root(root)
        manifest = json.loads((root / 'package.json').read_text())
        manifest['allowScripts'] = {'esbuild@0.28.2 || 0.28.1': False, 'fsevents': True}
        (root / 'package.json').write_text(json.dumps(manifest))
        lock = json.loads((root / 'package-lock.json').read_text())
        for name, version in (('esbuild', '0.28.2'), ('fsevents', '2.3.3')):
            lock['packages']['node_modules/' + name] = {
                'version': version, 'resolved': f'https://registry.npmjs.org/{name}/-/{name}-{version}.tgz'}
        (root / 'package-lock.json').write_text(json.dumps(lock))
        before = (root / 'package.json').read_bytes()
        helper['apply_profile_policy'](root)
        self.assertEqual((root / 'package.json').read_bytes(), before)

    def test_native_git_update_preserves_existing_checkout_and_handles_pinned_ref(self):
        profile = self.home / '.config/pi-work'
        source = 'git:github.com/example/test-kit@v1'
        (profile / 'settings.json').write_text(json.dumps({'packages': [source]}))
        root = profile / 'git/github.com/example/test-kit'
        self.dependency_root(root)
        sentinel = root / 'checkout-sentinel'
        sentinel.write_text('not deleted')
        result = self.run_task('--local-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel.read_text(), 'not deleted')
        self.assertIn(['pi', str(profile), ['update', source]], self.calls('pi'))
        self.assertEqual(len([c for c in self.calls('npm') if c[2][0] == 'audit']), 1)

    def test_raw_output_is_private_and_not_interleaved(self):
        result = self.run_task('--local-only', MOCK_PI_OUTPUT='raw spinner and clone chatter')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('raw spinner', result.stdout + result.stderr)
        logs = list((self.home / '.local/state/system-config/harness-refresh').glob('*/personal.log'))
        self.assertEqual(len(logs), 1)
        self.assertIn('raw spinner', logs[0].read_text())
        self.assertEqual(logs[0].stat().st_mode & 0o077, 0)
        self.assertEqual(logs[0].parent.stat().st_mode & 0o077, 0)

    def test_security_findings_are_not_installation_failures(self):
        self.dependency_root(self.home / '.config/pi-work/npm')
        audit = {'metadata': {'vulnerabilities': {'high': 2, 'moderate': 4, 'total': 6}},
                 'vulnerabilities': {'parent': {'fixAvailable': {
                     'name': 'parent', 'version': '4.3.1', 'isSemVerMajor': True}}}}
        result = self.run_task('--local-only', MOCK_AUDIT_JSON=json.dumps(audit), MOCK_AUDIT_RC='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SECURITY WARNING: 2 high, 4 moderate', result.stdout)
        self.assertIn('source-level major upgrade required: parent@4.3.1', result.stdout)
        summary = next((self.home / '.local/state/system-config/harness-refresh').glob('*/summary.json'))
        self.assertTrue(json.loads(summary.read_text())['security_findings'])

    def test_audit_errors_fail_instead_of_reporting_clean(self):
        self.dependency_root(self.home / '.config/pi/npm')
        for audit in ('not JSON', json.dumps({'error': {'code': 'ENETUNREACH'}}), '{}'):
            result = self.run_task('--local-only', MOCK_AUDIT_JSON=audit, MOCK_AUDIT_RC='1')
            self.assertEqual(result.returncode, 1)
            self.assertIn('SECURITY CHECK FAILED', result.stderr)
            self.assertNotIn('audit clean', result.stdout)

    def test_unreviewed_scripts_and_deprecations_remain_visible(self):
        root = self.home / '.config/pi-work/npm'
        self.dependency_root(root)
        lock = json.loads((root / 'package-lock.json').read_text())
        lock['packages']['node_modules/boolean'] = {'version': '3.2.0', 'deprecated': 'Unsupported'}
        (root / 'package-lock.json').write_text(json.dumps(lock))
        pending = {'allowScripts': [{'name': 'sharp', 'changes': [
            {'key': 'sharp@0.34.5', 'change': 'pending'}]}]}
        result = self.run_task('--local-only', MOCK_SCRIPTS_JSON=json.dumps(pending))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('unreviewed install scripts: sharp@0.34.5', result.stdout)
        self.assertIn('deprecated dependencies: boolean@3.2.0', result.stdout)

    def test_unexpected_npm_security_warnings_are_not_hidden(self):
        result = self.run_task('--local-only',
                               MOCK_PI_OUTPUT='npm warn install-scripts package.json policy is ignored')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('WARNING: install-scripts package.json policy is ignored', result.stdout)

    def test_script_report_failure_is_not_silenced(self):
        self.dependency_root(self.home / '.config/pi-work/npm')
        result = self.run_task('--local-only', MOCK_SCRIPTS_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('SECURITY CHECK FAILED', result.stderr)

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
        self.assertEqual(len([c for c in self.calls('pi') if c[2][0] == 'update']), 6)
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

    def test_update_system_local_only_refresh_after_successful_mac_rebuild(self):
        result = self.run_task(script=UPDATE, usage_switch_only='true', usage_harness_refresh='true',
                               usage_local_only='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('mise'), [
            ['mise', ['run', 'nix-rebuild', '--switch-only']],
            ['mise', ['run', 'harness-refresh', '--local-only']]])

    def test_update_system_failed_input_update_does_not_refresh(self):
        result = self.run_task(script=UPDATE, usage_harness_refresh='true', MOCK_REBUILD_RC='1')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls('mise'), [['mise', ['run', 'nix-rebuild', '--update-only']]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
