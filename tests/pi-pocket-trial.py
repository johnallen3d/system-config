#!/usr/bin/env python3
"""Installed Omarchy trial boundary; no model calls, auth-store reads or live DB open."""
import json
import sys
from pathlib import Path
import stat
import subprocess
import urllib.error
import urllib.request


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    home = Path.home()
    metadata = json.loads((home / '.config/pi-pocket-trial/deployment.json').read_text())
    assert metadata['revision'] == '26542deded0123d6b217828ed2f71f566d9a7a19'
    assert metadata['piVersion'] == '1.1.0'
    assert metadata['workspace'] == '/home/pi-pocket/notes'
    assert metadata['notesSource'] == str(home / 'notes')
    assert metadata['notesReadOnly'] is False
    profile = Path(metadata['privateHome']) / '.config/pi-pocket-trial'
    provider = json.loads((profile / 'models.json').read_text())['providers']['subscription-codex']
    assert provider['baseUrl'] == 'http://100.97.112.40:8317/v1'
    assert provider['api'] == 'openai-responses' and provider['authHeader'] is True
    assert provider['apiKey'].startswith('!/nix/store/')
    assert provider['apiKey'].endswith('/bin/cat ' + metadata['profile'] + '/proxy-client-key')
    assert {model['id'] for model in provider['models']} == {'gpt-6-luna', 'gpt-6.1-sol', 'gpt-6-astra'}
    key = profile / 'proxy-client-key'
    assert key.is_file() and not key.is_symlink()
    assert stat.S_IMODE(key.stat().st_mode) == 0o600 and key.stat().st_size > 0
    assert run('systemctl', '--user', 'is-active', metadata['service']) == 'active'
    assert run('systemctl', '--user', 'is-enabled', metadata['service']) == 'enabled'
    lock = subprocess.run(['flock', '--nonblock', str(Path(metadata['state']) / 'server.lock'), 'true'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert lock.returncode == 1, 'host-side one-writer lock is held'
    for directory in ('state', 'privateHome'):
        assert stat.S_IMODE(Path(metadata[directory]).stat().st_mode) == 0o700
    probe = r'''
set -euo pipefail
[[ "$HOME" == /home/pi-pocket ]]
[[ "$PI_CODING_AGENT_DIR" == /home/pi-pocket/.config/pi-pocket-trial ]]
[[ "$CLAUDE_CONFIG_DIR" == /home/pi-pocket/.config/claude-personal ]]
[[ "$PWD" == "$HOME/notes" ]]
# John authorized read/write for the entire project; other host mounts stay isolated.
notes_rw=0
while read -r id parent device root mountpoint options rest; do
  if [[ "$mountpoint" == "$HOME/notes" ]]; then
    [[ ",$options," == *,rw,* ]]
    notes_rw=1
  fi
done < /proc/self/mountinfo
[[ "$notes_rw" == 1 ]]
[[ "$VAULT_DIR" == "$HOME/notes" && "$VAULT_NAME" == "$VAULT_DIR" ]]
[[ "$NOTES_HELPER_PROVIDER" == subscription-codex && "$NOTES_HELPER_MODEL" == gpt-6-luna ]]
[[ "$NOTES_LABEL_TEXT_ONLY" == 1 ]]
command -v vlt python3 pi uv tesseract heif-convert >/dev/null
[[ "$(tesseract --list-langs 2>/dev/null)" == *eng* ]]
python3 -c 'import yaml; from PIL import Image, ImageOps'
pi --version >/dev/null
vlt vault="$VAULT_NAME" read file="templates/journal.md" >/dev/null
[[ "$(</proc/1/comm)" != systemd ]]
for absent in /home/johna /root /Users /run/user /run/dbus /etc/shadow /var/lib /tmp/host-pi-pocket-boundary; do
  test ! -e "$absent"
done
for variable in SSH_AUTH_SOCK DBUS_SESSION_BUS_ADDRESS TELEGRAM_BOT_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY; do
  test -z "${!variable-}"
done
# /nix/store remains read-only even though this UID owns store entries on some hosts.
! touch /nix/store/pi-pocket-must-not-write 2>/dev/null
file=$(mktemp /home/pi-pocket/scratch/.boundary-check.XXXXXX)
printf scratch > "$file"
test "$(cat "$file")" = scratch
rm "$file"
test -r "$PI_CODING_AGENT_DIR/AGENTS.md"
printf 'Read/write notes default, food runtime, PID, socket, environment and writable-scratch boundary passed\n'
'''
    # A host-only canary must not appear through /tmp inside the actual launcher.
    canary = Path('/tmp/host-pi-pocket-boundary')
    created = False
    try:
        with canary.open('x') as output:
            output.write('nonsecret boundary canary')
        created = True
        print(run(str(home / '.local/bin/pi-pocket-trial-sandbox'), 'bash', '-c', probe))
    finally:
        if created:
            canary.unlink()
    # Prove this is the real vault and supports updates/creation, without changing
    # an existing byte or leaving a synthetic note. O_TMPFILE is never linked.
    readwrite_probe = r'''
import json,os
from pathlib import Path
vault=Path.home()/'notes'
path=vault/'AGENTS.md'
assert path.is_file()
for target, flags in ((path, os.O_WRONLY), (vault, os.O_TMPFILE | os.O_RDWR)):
    fd=os.open(target, flags, 0o600)
    try:
        if target == vault:
            os.write(fd,b'nonsecret unlinked write probe')
            os.fsync(fd)
    finally:
        os.close(fd)
print(json.dumps({'device':vault.stat().st_dev,'inode':vault.stat().st_ino}))
'''
    observed = json.loads(run(str(home / '.local/bin/pi-pocket-trial-sandbox'),
                              str(Path(sys.executable).resolve()), '-c', readwrite_probe))
    actual = (home / 'notes').stat()
    assert observed == {'device': actual.st_dev, 'inode': actual.st_ino}
    print('Real-vault bind identity, write-only open and unlinked create/write passed; no existing vault bytes changed')
    host = run('/usr/bin/tailscale', 'ip', '-4')
    base = f'http://{host}:{metadata["port"]}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    assert opener.open(base, timeout=5).status == 200
    for asset in ('/app.js', '/vendor/preact.mjs', '/vendor/marked.mjs', '/vendor/purify.mjs'):
        assert opener.open(base + asset, timeout=5).status == 200
    try:
        opener.open(base + '/api/sessions', timeout=5)
        raise AssertionError('anonymous session access was accepted')
    except urllib.error.HTTPError as error:
        assert error.code == 401
    # Read the owner URL only deliberately, in memory; never print it or put it in argv.
    login = run(str(home / '.local/bin/pi-pocket-trial-login'))
    from urllib.parse import parse_qs, urlparse
    token = parse_qs(urlparse(login).query)['token'][0]
    def api(path):
        request = urllib.request.Request(base + '/api/' + path,
                                         headers={'Authorization': 'Bearer ' + token})
        with opener.open(request, timeout=10) as response:
            return json.load(response)
    me = api('me')
    assert me['server']['defaultCwd'] == metadata['workspace'], 'live server uses notes by default'
    assert {(model['provider'], model['id']) for model in me['models']} == {
        ('subscription-codex', model['id']) for model in provider['models']
    }, 'live Pocket runtime publishes exactly the three personal proxy models'
    assert isinstance(api('sessions'), list)
    modules = {item['file']: item for item in api('extensions')['modules']}
    for name in ('browser', 'gallery', 'goals', 'guard', 'memory', 'pip', 'schedules', 'subagents', 'triggers', 'agent-teams'):
        assert modules[name + '.ts']['enabled'] is False, name
    assert all(not item.get('error') for item in modules.values()), 'extension load error'
    assert modules['notes-search.ts']['enabled'] is True
    assert modules['notes-food.ts']['enabled'] is True
    search = [c for c in me['server']['extensionCommands'] if c['name'] == 'search']
    assert len(search) == 1 and search[0]['scope'] == 'conversation'
    food = [c for c in me['server']['extensionCommands'] if c['name'] == 'food']
    assert len(food) == 1 and food[0]['scope'] == 'global'
    # A same-name CLI prompt template must not hide the enabled helper command.
    for session in api('sessions'):
        if not session.get('archived'):
            assert not any(p['name'] == 'food' for p in api(f'c/{session["id"]}/prompts'))
    listener = f'{host}:{metadata["port"]}'
    sockets = run('ss', '-ltn')
    assert listener in sockets
    assert f'0.0.0.0:{metadata["port"]}' not in sockets
    assert f'127.0.0.1:{metadata["port"]}' not in sockets
    print('Installed package, private HTTP/API, disabled integrations and tailnet-only listener passed')
    print('Personal proxy configuration and private client-key permissions passed; no inference in this check')


if __name__ == '__main__':
    main()
