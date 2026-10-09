#!/usr/bin/env python3
"""Verify installed refresh results against upstream, without any model calls.

Run after harness-refresh on each host through its Amfaro mise context.
Uses only package metadata, Git refs, Pi's CLI, and the Claude MCP handshake.
"""

import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote
from urllib.request import urlopen


def command(*args, env=None, cwd=None):
    return subprocess.run(args, env=env, cwd=cwd, check=True, capture_output=True,
                          text=True, timeout=120).stdout.strip()


def latest_npm_version(name):
    with urlopen(f'https://registry.npmjs.org/{quote(name, safe="")}/latest', timeout=30) as response:
        return json.load(response)['version']


def git_head(directory):
    installed = command('git', '-C', str(directory), 'rev-parse', 'HEAD')
    remote = command('git', '-C', str(directory), 'ls-remote', 'origin', 'HEAD').split()[0]
    assert installed == remote, f'{directory}: installed {installed}, upstream {remote}'
    return installed


def main():
    home = Path.home()
    assert os.environ.get('PI_CODING_AGENT_DIR') == str(home / '.config/pi-work')
    assert os.environ.get('CLAUDE_CONFIG_DIR') == str(home / '.config/claude-gmatter')
    print('PASS effective work profile context')

    # Match the refresh worker: npx's /usr/bin/env node must not enter a mise
    # shim, which would re-select directory context over an explicit Pi profile.
    node = next(directory / 'node' for directory in (
        home / '.nix-profile/bin', Path('/etc/profiles/per-user') / os.environ['USER'] / 'bin',
        Path('/run/current-system/sw/bin'),
    ) if (directory / 'node').is_file())
    os.environ['PATH'] = f'{node.parent}:{os.environ["PATH"]}'
    pi = next(path for path in (
        home / '.local/bin/pi',
        Path('/etc/profiles/per-user') / os.environ['USER'] / 'bin/pi',
        home / '.nix-profile/bin/pi',
    ) if path.is_file())
    for profile in ('pi', 'pi-work', 'pi-notes'):
        directory = home / '.config' / profile
        settings = json.loads((directory / 'settings.json').read_text())
        packages = settings['packages']
        assert packages, f'{profile}: no declarations'
        for source in packages:
            assert isinstance(source, str), f'Unsupported declaration: {source}'
            if source.startswith('npm:'):
                name = source.removeprefix('npm:')
                metadata = json.loads((directory / 'npm/node_modules' / name / 'package.json').read_text())
                expected = latest_npm_version(name)
                assert metadata['version'] == expected, (profile, name, metadata['version'], expected)
                print(f'PASS {profile}: {name} {expected} matches npm latest')
            elif source.startswith('git:'):
                checkout = directory / 'git' / source.removeprefix('git:')
                assert (checkout / 'package.json').is_file(), checkout
                revision = git_head(checkout)
                print(f'PASS {profile}: {source} matches upstream HEAD {revision[:12]}')
            else:
                raise AssertionError(f'Unsupported declaration: {source}')
        env = dict(os.environ, PI_CODING_AGENT_DIR=str(directory))
        listing = command(str(pi), 'list', env=env)
        for source in packages:
            assert source in listing, (profile, source, listing)
        print(f'PASS {profile}: Pi CLI discovers all declared packages')

    runtime = command(str(pi), '--version')
    expected = latest_npm_version('@earendil-works/pi-coding-agent')
    assert runtime.splitlines()[-1] == expected, (runtime, expected)
    print(f'PASS Pi runtime {expected} matches npm latest')

    claude_dir = home / '.config/claude-gmatter'
    marketplace = claude_dir / 'plugins/marketplaces/amfaro'
    git_head(marketplace)
    expected = json.loads((marketplace / '.claude-plugin/plugin.json').read_text())['version']
    plugins = json.loads(command(str(home / '.local/bin/claude'), 'plugin', 'list', '--json'))
    plugin = next(item for item in plugins if item['id'] == 'agent-kit@amfaro' and item['scope'] == 'user')
    assert plugin['enabled'] and plugin['version'] == expected, plugin
    print(f'PASS work Claude plugin {expected} enabled; marketplace matches upstream HEAD')

    checkout = home / '.config/pi-work/git/github.com/amfaro/agent-kit'
    command(str(node), '-e', """
const sharp = require('sharp');
sharp({create:{width:1,height:1,channels:3,background:'#000'}}).png().toBuffer()
  .then(bytes => { if (!bytes.length) process.exit(1); })
  .catch(error => { console.error(error); process.exit(1); });
""", cwd=checkout)
    print('PASS refreshed work Pi kit: Sharp native image processing')

    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'harness-refresh-smoke', 'version': '1'},
        }},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
    ]
    result = subprocess.run(
        [str(node), str(Path(plugin['installPath']) / 'claude-code/mcp-server.ts')],
        input=''.join(json.dumps(request) + '\n' for request in requests),
        capture_output=True, text=True, timeout=30, check=True,
    )
    replies = {reply['id']: reply for line in result.stdout.splitlines()
               if (reply := json.loads(line)).get('id') is not None}
    assert 'result' in replies[1], replies[1]
    tools = {tool['name'] for tool in replies[2]['result']['tools']}
    assert {'find_tools', 'call_tool'} <= tools, tools
    print('PASS refreshed Claude MCP: startup, initialize, tools/list')


if __name__ == '__main__':
    main()
