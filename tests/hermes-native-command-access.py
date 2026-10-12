#!/usr/bin/env python3
"""#774: original terminal approval behavior and isolated real task fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'modules/home-manager/hermes-native'
spec = importlib.util.spec_from_file_location('command_access_runtime', ASSETS / 'production-runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class TerminalAccess(unittest.TestCase):
    def test_original_commands_keep_arguments_and_approval_result(self):
        broker = mock.Mock(side_effect=AssertionError('not a broker command'))
        pending = json.dumps({'status': 'pending_approval', 'approval_pending': True})
        original = mock.Mock(return_value=pending)
        for command in ['mise tasks ls', 'mise run get-weather', 'mise run nlm -- --help',
                        'mise run recipe-tables -- --dry-run', 'mise run weight -- 180.1',
                        'mise run macros -- 2030-01-01', 'bash -c "echo fixture"',
                        'printf fixture | wc -c', 'rm -rf /tmp/SYNTHETIC']:
            with self.subTest(command=command):
                arguments = {'command': command, 'workdir': '$VAULT_DIR', 'timeout': 30}
                self.assertEqual(runtime.dispatch_terminal(arguments, broker, original, task_id='fixture'), pending)
                original.assert_called_with(arguments, task_id='fixture')
        broker.assert_not_called()

    def test_native_failure_never_retries_through_original_tool(self):
        broker = mock.Mock(side_effect=OSError('uncertain write'))
        original = mock.Mock(side_effect=AssertionError('must not retry'))
        result = runtime.dispatch_terminal({'command': 'vlt vault=Personal append file=journal/2030-01-01.md content=SYNTHETIC'}, broker, original)
        self.assertEqual(json.loads(result)['exit_code'], 64)
        self.assertEqual(broker.call_args.args[0]['operation'], 'vault')
        broker.assert_called_once()
        original.assert_not_called()

    def test_calendar_and_native_adapter_parse_failures_stay_closed(self):
        original = mock.Mock()
        broker = mock.Mock()
        for command in ['mise run gog -- auth login', 'mise run gog-auth-bootstrap',
                        'mise run gog -- gmail list', 'mise run save-recipe -- INVALID']:
            with self.subTest(command=command):
                self.assertEqual(json.loads(runtime.dispatch_terminal({'command': command}, broker, original))['exit_code'], 64)
        original.assert_not_called()
        broker.assert_not_called()

    def test_gateway_has_original_vault_access_but_readonly_controller(self):
        metadata = mock.Mock()
        immutable = mock.Mock()
        immutable.__str__ = mock.Mock(return_value='/nix/store/SYNTHETIC-production.json')
        metadata.resolve.return_value = immutable
        m = {'paths': {'state': '/synthetic/state', 'home': '/synthetic/home',
                       'config': '/synthetic/config', 'cache': '/synthetic/cache'},
             'vault': '/synthetic/notes', 'bubblewrap': '/synthetic/bwrap',
             'envBinary': '/synthetic/env', 'bashBinary': '/synthetic/bash',
             'python': '/synthetic/python', 'managedAssets': '/synthetic/assets'}
        immutable.read_bytes.return_value = json.dumps(m).encode()
        with mock.patch.object(runtime.t, 'PRODUCTION_METADATA', metadata), \
                mock.patch.object(runtime, 'live_owner', return_value={'phase': 'NATIVE_LIVE'}):
            argv = runtime.gateway_command(m)
        with mock.patch.object(runtime.t, 'PRODUCTION_METADATA', metadata), \
                mock.patch.object(runtime, 'live_owner', return_value={'phase': 'NATIVE_ARMED'}):
            armed = runtime.gateway_command(m)
        self.assertEqual(armed[armed.index(m['vault']) - 1], '--ro-bind')
        i = argv.index(m['vault'])
        self.assertEqual(argv[i - 1:i + 2], ['--bind', m['vault'], '/synthetic/state/workspace/notes'])
        i = argv.index('/synthetic/state/controller')
        self.assertEqual(argv[i - 1], '--ro-bind')
        self.assertIn('--tmpfs', argv)
        self.assertNotIn('/home/johna/.config/pi', argv)


@unittest.skipUnless(os.environ.get('HERMES774_METADATA'), 'installed Linux task fixture requires explicit metadata')
class OriginalTaskFixture(unittest.TestCase):
    def test_real_tasks_in_private_namespace_without_production_notes_or_credentials(self):
        m = json.loads(Path(os.environ['HERMES774_METADATA']).read_bytes())
        vault = Path(m['vault'])
        with tempfile.TemporaryDirectory(prefix='hermes774-') as temporary:
            root = Path(temporary)
            notes = root / 'notes'
            notes.mkdir()
            shutil.copytree(vault / '.mise/tasks', notes / '.mise/tasks')
            (notes / 'mise.toml').write_text((vault / 'mise.toml').read_text())
            (notes / 'templates').mkdir()
            (notes / 'templates/journal.md').write_text('---\ntags: [journal]\n---\n# {{date}}\n\n## Log\n')
            (notes / 'recipes').mkdir()
            (notes / 'recipes/fixture.md').write_text('# Fixture\n\n#recipe\n\n## Ingredients\n\n- 1 cup water\n\n## Steps\n\n1. Stir.\n')
            (root / 'home').mkdir()
            (root / 'state').mkdir()
            (root / 'config').mkdir()
            (root / 'cache').mkdir()
            # Use the original provider task's explicit fixture-input interface.
            (notes / 'weather-fixture.json').write_text(json.dumps({
                'current_condition': [{'weatherDesc': [{'value': 'SYNTHETIC WEATHER'}],
                                       'temp_F': '55', 'FeelsLikeF': '54', 'humidity': '50'}],
                'weather': [{'maxtempF': '60', 'mintempF': '45'}]}))
            state = '/fixture/hermes-native/production/baseline-0.21.2'
            alias = state + '/workspace/notes'
            env = dict(m['environment'])
            env.update(HOME='/fixture/home', HERMES_HOME=state,
                       VAULT_DIR=alias, VLT_VAULT_PATH=alias,
                       MISE_TRUSTED_CONFIG_PATHS=alias, MISE_CONFIG_DIR='/fixture/config/mise',
                       MISE_DATA_DIR='/fixture/home/.local/share/mise', MISE_CACHE_DIR='/fixture/cache/mise',
                       MISE_DISABLE_TOOLS='uv,sd,yq,npm:defuddle', HERMES_NATIVE_STAGE='production',
                       HERMES_NATIVE_TASK_ACCESS='original', NOTEBOOKLM_HOME='/fixture/home/.notebooklm',
                       XDG_CONFIG_HOME='/fixture/config', XDG_CACHE_HOME='/fixture/cache',
                       XDG_DATA_HOME='/fixture/home/.local/share', XDG_STATE_HOME='/fixture/home/.local/state',
                       PATH=env['HERMES_NATIVE_TASK_PATH'])
            for key in ['GOG_KEYRING_PASSWORD', 'TELEGRAM_BOT_TOKEN', 'HERMES_PRODUCTION_BROKER_FD']:
                env.pop(key, None)
            argv = [m['bubblewrap'], '--unshare-all', '--die-with-parent', '--new-session',
                    '--ro-bind', '/nix/store', '/nix/store', '--proc', '/proc', '--dev', '/dev',
                    '--tmpfs', '/tmp', '--dir', '/usr', '--dir', '/usr/bin', '--dir', '/bin',
                    '--symlink', m['envBinary'], '/usr/bin/env', '--symlink', m['bashBinary'], '/bin/bash',
                    '--symlink', m['bashBinary'], '/bin/sh', '--dir', '/fixture',
                    '--bind', str(root / 'home'), '/fixture/home', '--bind', str(root / 'state'), state,
                    '--bind', str(notes), alias, '--bind', str(root / 'config'), '/fixture/config',
                    '--bind', str(root / 'cache'), '/fixture/cache',
                    '--chdir', alias]
            commands = [(['tasks', 'ls', '--json'], 'weight'),
                        (['run', 'weight', '--', '180.1'], '180.1'),
                        (['run', 'get-weather', '--', '--input-file=' + alias + '/weather-fixture.json'], 'SYNTHETIC WEATHER'),
                        (['run', 'nlm', '--', '--help'], 'NotebookLM'),
                        (['run', 'recipe-tables', '--', '--dry-run'], 'recipes/fixture.md')]
            for args, expected in commands:
                with self.subTest(args=args):
                    result = subprocess.run([*argv, env['HERMES_NATIVE_MISE'], *args], env=env,
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr.decode()[-1800:])
                    self.assertIn(expected.lower(), result.stdout.decode().lower())
            daily = list((notes / 'journal').rglob('*.md'))
            self.assertEqual(len(daily), 1)
            self.assertIn('weight:: 180.1', daily[0].read_text())
            self.assertEqual((notes / 'recipes/fixture.md').read_text(),
                             '# Fixture\n\n#recipe\n\n## Ingredients\n\n- 1 cup water\n\n## Steps\n\n1. Stir.\n')


if __name__ == '__main__':
    unittest.main()
