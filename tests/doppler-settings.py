#!/usr/bin/env python3
"""Check managed Doppler settings without API calls or displaying credentials.

Default: exercise the native host's real Nix-generated setter in an isolated home.
--record-before PATH / --installed --before PATH: verify host-local preservation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {
    'dev/src/amfaro/calc': ('calc', 'dev'),
    'dev/src/amfaro/cookbook': ('shared', 'dev'),
    'dev/src/amfaro/dataops': ('dataops', 'dev'),
    'dev/src/amfaro/docs': ('shared', 'prod'),
    'dev/src/amfaro/global-catalog': ('global-catalog', 'dev'),
    'dev/src/playground/home-assistant': ('home-assistant', 'prod'),
    'dev/src/playground/music-library': ('music-library', 'dev'),
    'dev/src/playground/pi-cielo': ('pi-cielo', 'prod'),
    'dev/src/system-config': ('system-config', 'dev_personal'),
    'notes': ('notes', 'prd'),
}
ENDPOINTS = {'api-host': 'https://api.doppler.com',
             'dashboard-host': 'https://dashboard.doppler.com'}


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, timeout=180, **kwargs)
    if result.returncode:
        # Do not include config contents or subprocess output in failures.
        raise RuntimeError(f'Command failed: {Path(args[0]).name} (exit {result.returncode})')
    return result.stdout


def tools():
    attribute = ('darwinConfigurations.m4-mbp.config.home-manager.users."john.allen"'
                 if sys.platform == 'darwin' else 'homeConfigurations."johna@omarchy".config')
    target = f'path:{ROOT}#{attribute}.home.activation.dopplerManagedSettings.data'
    activation = run(['nix', 'eval', '--raw', '--no-write-lock-file', target])
    context = json.loads(run(['nix', 'eval', '--json', '--no-write-lock-file', target,
                              '--apply', 'builtins.getContext']))
    drv = next(key for key in context if key.endswith('-doppler-managed-settings.drv'))
    run(['nix-store', '--realise', drv])
    setter = Path(re.search(r'(/nix/store/\S+/bin/doppler-managed-settings)', activation)[1])
    source = setter.read_text()
    yq = re.search(r'(/nix/store/[^:]+-yq-go-[^:]+/bin)', source)[1] + '/yq'
    doppler = re.search(r'(/nix/store/\S+/bin/doppler) --no-read-env', source)[1]
    return source, yq, doppler


def load(yq, home):
    path = home / '.doppler/.doppler.yaml'
    return json.loads(run([yq, '-o=json', '.', str(path)])) if path.exists() else {}


def preservation(state, home):
    # Hash all fields not owned by this module, including every retained token.
    copy = json.loads(json.dumps(state))
    scopes = copy.get('scoped', {})
    obsolete = str(home / '.supacode/repos')
    for scope in list(scopes):
        if scope == obsolete or scope.startswith(obsolete + '/'):
            del scopes[scope]
    for key in ENDPOINTS:
        scopes.get('/', {}).pop(key, None)
    for relative in PROJECTS:
        fields = scopes.get(str(home / relative), {})
        for key in ('enclave.project', 'enclave.config'):
            fields.pop(key, None)
        if relative == 'notes' or relative.startswith('dev/src/playground/'):
            for key in ENDPOINTS:
                fields.pop(key, None)
    copy['scoped'] = {key: value for key, value in scopes.items() if value}
    return hashlib.sha256(json.dumps(copy, sort_keys=True).encode()).hexdigest()


def check(state, home):
    scopes = state['scoped']
    assert all(scopes['/'].get(key) == value for key, value in ENDPOINTS.items())
    for relative, (project, config) in PROJECTS.items():
        fields = scopes[str(home / relative)]
        assert fields['enclave.project'] == project, relative
        assert fields['enclave.config'] == config, relative
    obsolete = str(home / '.supacode/repos')
    assert not any(key == obsolete or key.startswith(obsolete + '/') for key in scopes)
    path = home / '.doppler/.doppler.yaml'
    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_mode & 0o777 == 0o600
    assert (home / '.doppler').stat().st_mode & 0o777 == 0o700
    assert not list((home / '.doppler').glob('.managed-settings.*'))


def isolated(source, yq, doppler):
    with tempfile.TemporaryDirectory(prefix='doppler-settings-') as tmp:
        home = Path(tmp)
        directory = home / '.doppler'
        directory.mkdir(mode=0o700)
        path = directory / '.doppler.yaml'
        original = {'introVersionSeen': 7, 'scoped': {
            '/': {'token': 'synthetic-personal'},
            str(home / 'dev/src/amfaro'): {'token': 'synthetic-work'},
            str(home / 'dev/src/amfaro/calc'): {'token': 'synthetic-child', 'verify-tls': False},
            str(home / '.supacode/repos'): {'token': 'synthetic-obsolete'},
            str(home / '.supacode/repos/calc/task'): {'enclave.project': 'old'},
            str(home / '.supacode/repos-other'): {'token': 'synthetic-unrelated'},
            str(home / 'unrelated'): {'enclave.project': 'keep', 'custom': 'keep'},
        }}
        path.write_text(json.dumps(original))
        setter = home / 'setter.sh'
        setter.write_text(source.replace(str(Path.home()), str(home)))
        command = [source.splitlines()[0][2:], str(setter)]
        env = dict(os.environ, HOME=str(home), DOPPLER_TOKEN='synthetic-environment',
                   DOPPLER_PROJECT='wrong', DOPPLER_CONFIG='wrong')
        result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=180)
        assert result.returncode == 0, result.stderr  # Isolated synthetic state only.
        assert 'synthetic-' not in result.stdout
        state = load(yq, home)
        assert preservation(original, home) == preservation(state, home)
        check(state, home)
        before = path.read_bytes()
        run(command, env=env)
        assert before == path.read_bytes(), 'setter must be idempotent'
        # Native CLI resolves project/config from the generated scoped settings.
        resolved = run([doppler, '--no-read-env', '--no-check-version', '--config-dir', str(directory),
                        'configure', 'get', 'project', 'config', '--scope',
                        str(home / 'dev/src/amfaro/docs'), '--json'], env=env)
        assert 'shared' in resolved and 'prod' in resolved
        path.unlink()
        run(command, env=env)
        state = load(yq, home)
        check(state, home)
        assert not any('token' in fields for fields in state['scoped'].values())
        target = home / 'credentials-local.yaml'
        target.write_text('scoped: {}\n')
        path.unlink()
        path.symlink_to(target)
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        assert result.returncode != 0 and target.read_text() == 'scoped: {}\n'
    print('PASS scoped settings, token/state preservation, Supacode cleanup, permissions, '
          'idempotence, fresh host, environment isolation, native CLI resolution, symlink guard')


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--record-before', type=Path)
parser.add_argument('--installed', action='store_true')
parser.add_argument('--before', type=Path)
args = parser.parse_args()
source, yq, doppler = tools()
if args.record_before:
    args.record_before.write_text(json.dumps({'preservation': preservation(load(yq, Path.home()), Path.home())}))
    args.record_before.chmod(0o600)
    print('Recorded host-local preservation fingerprint; no credentials stored')
elif args.installed:
    state = load(yq, Path.home())
    check(state, Path.home())
    if args.before:
        assert json.loads(args.before.read_text())['preservation'] == preservation(state, Path.home())
    resolved = run([doppler, '--no-read-env', '--no-check-version', 'configure', 'get',
                    'project', 'config', '--scope', str(Path.home() / 'dev/src/amfaro/docs'), '--json'])
    assert 'shared' in resolved and 'prod' in resolved
    print('PASS installed managed scopes, local-state preservation, private writable file, native CLI resolution')
else:
    isolated(source, yq, doppler)
