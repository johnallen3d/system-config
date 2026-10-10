#!/usr/bin/env python3
"""Shared personal/work footer regressions; no model calls or credential writes.

--evaluate checks both hosts' real Nix activation merges in an isolated home.
--installed checks activated settings and actual renderer output in both profiles.
--record-before PATH / --before PATH verify unrelated settings and auth preservation.
--reference PATH compares presentation byte-for-byte with the work plugin renderer.
The historical filename is retained for existing deployment commands.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / 'modules/home-manager/claude-statusline/statusline.mjs'
PROFILES = ('claude-personal', 'claude-gmatter')


def run(command, env=None, data='{}'):
    return subprocess.run(command, env=env, input=data, text=True,
                          capture_output=True, check=True, timeout=90).stdout


# Resolve outside temporary HOME so mise's shim does not re-evaluate trust there.
NODE = run(['node', '-p', 'process.execPath']).strip()


def payload(directory, percent=25, model='Claude Opus'):
    return {'model': {'display_name': model},
            'context_window': {'context_window_size': 200000, 'used_percentage': percent,
                               'current_usage': {'input_tokens': 40000,
                                                 'cache_read_input_tokens': 9000,
                                                 'cache_creation_input_tokens': 1000,
                                                 'output_tokens': 99999}},
            'workspace': {'current_dir': str(directory)},
            'worktree': {'branch': 'feature/personal'}}


def preservation():
    result = {}
    for profile in PROFILES:
        directory = Path.home() / '.config' / profile
        settings = json.loads((directory / 'settings.json').read_text())
        settings.pop('statusLine', None)
        if profile == 'claude-gmatter':
            settings.pop('outputStyle', None)
        result[profile + '/settings'] = hashlib.sha256(
            json.dumps(settings, sort_keys=True).encode()).hexdigest()
        for name in ('.credentials.json', 'auth.json', '.claude.json',
                     'plugins/installed_plugins.json'):
            path = directory / name
            result[profile + '/' + name] = (hashlib.sha256(path.read_bytes()).hexdigest()
                                          if path.exists() else None)
    return result


def offline(reference):
    with tempfile.TemporaryDirectory(prefix='claude footer ') as tmp:
        root = Path(tmp)
        for profile in PROFILES:
            env = dict(os.environ, HOME=tmp, CLAUDE_CONFIG_DIR=str(root / profile),
                       PI_CODING_AGENT_DIR=str(root / ('pi' if profile == 'claude-personal' else 'pi-work')))
            # No profile directory, plugin, settings, or credentials exist here.
            for percent, color in ((25, False), (70, True), (71, True), (90, True), (91, True)):
                if color:
                    env.pop('NO_COLOR', None)
                else:
                    env['NO_COLOR'] = '1'
                data = json.dumps(payload(root, percent))
                output = run([NODE, str(RENDERER)], env, data)
                expected_ctx = f'ctx 50k/200k {percent}%'
                assert expected_ctx in output and 'Claude Opus' in output, output
                assert f'{root.name} · feature/personal' in output, output
                assert len(output.rstrip().split('\n')) == 2, output
                code = '\x1b[31m' if percent > 90 else '\x1b[33m' if percent > 70 else ''
                assert (code + expected_ctx) in output, output
                assert ('\x1b[' in output) == color, output
                if reference:
                    assert output == run([NODE, str(reference)], env, data), output
            env['NO_COLOR'] = '1'
            for data in ('{}', 'not json'):
                assert run([NODE, str(RENDERER)], env, data) == 'ctx 0/200k 0%\n'
            fallback = {'model': {'id': 'personal-model'}, 'cwd': str(root),
                        'context_window': {'context_window_size': 1000000,
                                           'current_usage': {'input_tokens': 100000}}}
            assert 'ctx 100k/1.0M 10% | personal-model' in run(
                [NODE, str(RENDERER)], env, json.dumps(fallback))
        run(['git', 'init', '-q', '-b', 'feature/git-branch', str(root)])
        output = run([NODE, str(RENDERER)], env, json.dumps(payload(root)))
        assert 'feature/git-branch' in output and 'feature/personal' not in output, output
    print('PASS shared two-line presentation, token accounting, colors, branch, malformed input, profile isolation')


def evaluate():
    attributes = (
        'darwinConfigurations.m4-mbp.config.home-manager.users."john.allen"',
        'homeConfigurations."johna@omarchy".config',
    )
    for attribute in attributes:
        script = run(['nix', '--extra-experimental-features', 'nix-command flakes',
                      'eval', '--impure', '--raw', '--no-write-lock-file',
                      f'path:{ROOT}#{attribute}.home.activation.claudeGmatterSettings.data'])
        # Test the evaluated merge without building cross-platform runtime tools.
        native_path = os.pathsep.join(p for p in os.environ['PATH'].split(os.pathsep)
                                      if '/shims' not in p)
        for tool in ('jq', 'mktemp'):
            script = re.sub(r'/nix/store/[^\s"/]+/bin/' + tool,
                            shutil.which(tool, path=native_path), script)
        with tempfile.TemporaryDirectory(prefix='claude activation ') as tmp:
            home = Path(tmp)
            original = {'model': 'saved-personal-model', 'outputStyle': 'personal-style',
                        'env': {'PRIVATE': 'preserved'}, 'hooks': {'custom': ['keep']},
                        'statusLine': {'command': 'old', 'interval': 123}}
            for profile in PROFILES:
                path = home / '.config' / profile / 'settings.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(original))
            env = dict(os.environ, HOME=tmp, DRY_RUN_CMD='echo')
            run(['bash', '-eu', '-c', script], env)
            assert all(json.loads((home / '.config' / p / 'settings.json').read_text()) == original
                       for p in PROFILES)
            env['DRY_RUN_CMD'] = ''
            run(['bash', '-eu', '-c', script], env)
            once = []
            for profile in PROFILES:
                path = home / '.config' / profile / 'settings.json'
                value = json.loads(path.read_text())
                assert value['statusLine']['padding'] == 0
                assert 'interval' not in value['statusLine']
                assert value['outputStyle'] == ('ELI5' if profile == 'claude-gmatter' else 'personal-style')
                for key in ('model', 'env', 'hooks'):
                    assert value[key] == original[key]
                assert path.stat().st_mode & 0o777 == 0o600
                once.append(path.read_bytes())
            run(['bash', '-eu', '-c', script], env)
            assert once == [(home / '.config' / p / 'settings.json').read_bytes() for p in PROFILES]
            personal = home / '.config/claude-personal/settings.json'
            personal.write_text('broken JSON')
            result = subprocess.run(['bash', '-eu', '-c', script], env=env, capture_output=True)
            assert result.returncode != 0 and personal.read_text() == 'broken JSON'
            assert not list(personal.parent.glob('settings.json.*'))
        print('PASS evaluated activation: preservation, complete footer replacement, dry-run, idempotence, invalid JSON:', attribute)


def installed(before):
    statuses = []
    outputs = []
    for profile in PROFILES:
        path = Path.home() / '.config' / profile / 'settings.json'
        settings = json.loads(path.read_text())
        status = settings['statusLine']
        assert status['type'] == 'command' and status['padding'] == 0
        assert status['command'].startswith('/nix/store/')
        assert not path.is_symlink() and path.stat().st_mode & 0o777 == 0o600
        statuses.append(status)
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(path.parent),
                   PI_CODING_AGENT_DIR=str(Path.home() / '.config' /
                                          ('pi' if profile == 'claude-personal' else 'pi-work')),
                   NO_COLOR='1')
        data = json.dumps(payload(ROOT, model=profile + '-model'))
        output = run(['bash', '-c', status['command']], env, data)
        assert 'ctx 50k/200k 25%' in output and profile + '-model' in output, output
        assert ROOT.name in output and len(output.rstrip().split('\n')) == 2, output
        assert output == run([NODE, str(RENDERER)], env, data), output
        outputs.append(output.replace(profile + '-model', 'model'))
    assert statuses[0] == statuses[1] and outputs[0] == outputs[1]
    if before:
        old = json.loads(before.read_text())
        current = preservation()
        changed = [key for key in old if old[key] != current[key]]
        # Claude itself updates .claude.json metadata in active sessions/CLI calls.
        # Observe it, but gate only settings, credentials, and plugin registration.
        assert not [key for key in changed if not key.endswith('/.claude.json')], \
            'Unrelated settings/auth/plugin state changed: ' + ', '.join(changed)
        if changed:
            print('NOTE mutable Claude runtime metadata changed during deployment:', ', '.join(changed))
    print('PASS installed personal/work identical footer commands and rendering; profile-appropriate models and preservation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evaluate', action='store_true')
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--record-before', type=Path)
    parser.add_argument('--before', type=Path)
    args = parser.parse_args()
    if args.record_before:
        args.record_before.touch(mode=0o600)
        args.record_before.chmod(0o600)
        args.record_before.write_text(json.dumps(preservation(), sort_keys=True))
        print('Recorded preservation hashes only')
        return
    offline(args.reference)
    if args.evaluate:
        evaluate()
    if args.installed:
        installed(args.before)


if __name__ == '__main__':
    main()
