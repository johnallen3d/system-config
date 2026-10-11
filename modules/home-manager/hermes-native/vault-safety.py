#!/usr/bin/env python3
"""#759 fixed read confinement plus operator-only status/snapshot.

No production mutation/restore/enable command exists. Never prints private file
names, contents, link targets, credentials or raw REST errors. Snapshot restores
are verified ONLY in a new private non-synchronized directory.
"""
from __future__ import annotations
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

PRODUCTION = Path('/home/johna/notes')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def manifest(root):
    """No symlink traversal; reject special files. All names stay private."""
    rows = {}
    def visit(path):
        s = path.lstat()
        row = {'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid,
               'mtime_ns': s.st_mtime_ns}
        if stat.S_ISLNK(s.st_mode):
            row.update(type='link', target=os.readlink(path))
        elif stat.S_ISDIR(s.st_mode):
            row['type'] = 'dir'
        elif stat.S_ISREG(s.st_mode):
            row.update(type='file', size=s.st_size, sha256=digest(path))
            after = path.lstat()
            if (s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise RuntimeError('source moved during manifest')
        else:
            raise RuntimeError('special file refused')
        row['xattrs'] = {n: os.getxattr(path, n, follow_symlinks=False).hex()
                        for n in sorted(os.listxattr(path, follow_symlinks=False))}
        rows[path.relative_to(root).as_posix()] = row
        if row['type'] == 'dir':
            for p in sorted(path.iterdir()):
                visit(p)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError('linked/non-directory root refused')
    visit(root)
    return rows


def tree_flags(root):
    counts = dict(conflicts=0, temporary=0, links=0, special=0)
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(base) / name
            mode = p.lstat().st_mode
            counts['conflicts'] += '.sync-conflict-' in name
            counts['temporary'] += ((name.startswith('.syncthing.') and name.endswith('.tmp')) or
                                    name.startswith('.atomic-') or name.endswith('.md.tmp') or '.md.tmp.' in name)
            counts['links'] += stat.S_ISLNK(mode)
            counts['special'] += not (stat.S_ISLNK(mode) or stat.S_ISDIR(mode) or stat.S_ISREG(mode))
    return counts


def local_api(endpoint, *, scan=False):
    config = Path('/home/johna/.local/state/syncthing/config.xml')
    if not config.exists(): config = Path('/home/johna/.config/syncthing/config.xml')
    root = ET.parse(config).getroot()
    key = root.findtext('gui/apikey')
    request = urllib.request.Request('http://127.0.0.1:8384'+endpoint,
        headers={'X-API-Key':key},method='POST' if scan else 'GET')
    with urllib.request.urlopen(request,timeout=15) as response:
        data=response.read()
        return json.loads(data) if data else None


def scan_content(names):
    """Existing local GUI scan; no pause, new instance or peer reconfiguration."""
    for name in names:
        path=Path(name)
        if path.is_absolute() or any(q in {'.','..'} for q in path.parts) or path.as_posix()!=name:
            raise RuntimeError('scan content path refused')
        local_api('/rest/db/scan?'+urllib.parse.urlencode({'folder':'notes','sub':name}),scan=True)


def local_status():
    # Timestamp the beginning, not completion, of real API observations. Slow
    # requests cannot be made fresh by stamping cached evidence afterwards.
    observed_at=time.time()
    get=local_api
    my_id = get('/rest/system/status')['myID']
    folders = [x for x in get('/rest/config/folders') if x['id'] == 'notes']
    if len(folders) != 1 or Path(folders[0]['path']) != PRODUCTION or PRODUCTION.is_symlink():
        raise RuntimeError('folder identity/path changed')
    folder = folders[0]
    status = get('/rest/db/status?folder=notes')
    connections = get('/rest/system/connections')['connections']
    peers = [x['deviceID'] for x in folder['devices'] if x['deviceID'] != my_id]
    peer_ok = True
    for peer in peers:
        c = get('/rest/db/completion?folder=notes&device=' + peer)
        peer_ok &= (connections.get(peer, {}).get('connected') is True and
                    c.get('completion') == 100 and c.get('remoteState') == 'valid' and
                    all(c.get(k) == 0 for k in ['needBytes', 'needItems', 'needDeletes']))
    errors = get('/rest/folder/errors?folder=notes').get('errors') or []
    clean = (status.get('state') == 'idle' and not folder['paused'] and
             folder['type'] == 'sendreceive' and not errors and
             all(status.get(k) == 0 for k in ['errors', 'pullErrors', 'needFiles',
                  'needDirectories', 'needSymlinks', 'needDeletes', 'needBytes', 'needTotalItems']) and
             not any(status.get(k) for k in ['error', 'invalid', 'watchError']))
    flags = tree_flags(PRODUCTION)
    return {'folder': 'notes', 'path': str(PRODUCTION), 'type': folder['type'],'observedAt':observed_at,
            'state': status.get('state'), 'directPeerCount': len(peers),
            'localConvergence': bool(clean), 'directPeerConvergence': bool(peers and peer_ok),
            'versioning': bool(folder['versioning']['type']), **flags,
            'productionWrites': 'DISABLED',
            'writeGate': 'STOP' if not clean or not peer_ok or flags['conflicts'] or flags['temporary'] or flags['special'] else 'LOCAL-ONLY; all-peer writer/rollback approval still required'}


def private_json(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, sort_keys=True)
        stream.write('\n')
    path.chmod(0o600)


def snapshot(source, destination):
    """Exact copy, including xattrs/links, with before/after drift detection.

    This stable live observation is NOT global writer quiescence, an iCloud
    backup guarantee, or permission to restore any peer. No production pause.
    """
    import shutil
    before = manifest(source)
    destination.mkdir(mode=0o700)
    def copy_tree(target):
        shutil.copytree(source, target, symlinks=True, copy_function=shutil.copy2)
    tree = destination / 'tree'
    copy_tree(tree)
    copied = manifest(tree)
    after = manifest(source)
    if before != after or copied != before:
        raise RuntimeError('snapshot drift/integrity mismatch; retain private failed copy')
    # Private root hides original modes. Do not change copied modes or follow links.
    private_json(destination / 'manifest.json', before)
    restored = destination / 'restore-disposable'
    shutil.copytree(tree, restored, symlinks=True, copy_function=shutil.copy2)
    if manifest(restored) != before:
        raise RuntimeError('disposable restore mismatch')
    payload = json.dumps(before, sort_keys=True).encode()
    result = {'entries': len(before), 'manifestSha256': hashlib.sha256(payload).hexdigest(),
              'integrity': 'PASS', 'disposableRestore': 'PASS', 'sourceStableAcrossCopy': True,
              'productionRestore': 'NOT AUTHORIZED', 'globalQuiescence': 'NOT PROVEN'}
    private_json(destination / 'receipt.json', result)
    return result


def read_check():
    """Fixed Nix-owned read operation: no arguments, tasks or mutable scripts."""
    root = Path('/vault-readonly')
    assert os.environ.get('HERMES_VAULT_MODE') == 'read-only'
    assert not PRODUCTION.exists() and not Path('/run/user/1000').exists()
    assert not any(k.startswith(('PI_', 'CLAUDE_')) or k.endswith(('TOKEN', 'API_KEY')) for k in os.environ)
    mount = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()
             if line.split()[4] == str(root)]
    assert len(mount) == 1 and 'ro' in mount[0][5].split(',')
    # Open without O_TRUNC/O_CREAT: never changes bytes even if a regression is detected.
    files = []
    journal = root / 'journal'
    assert journal.is_dir() and not journal.is_symlink(), 'regular journal root required'
    # Root governance files can be deliberately excluded by the vault's vlt
    # index. Select an actual journal note, not a copied automation/config file.
    for base, dirs, names in os.walk(journal, followlinks=False):
        dirs[:] = [x for x in dirs if not (Path(base) / x).is_symlink()]
        for name in sorted(names):
            p = Path(base) / name
            if name.endswith('.md') and stat.S_ISREG(p.lstat().st_mode):
                files.append(p)
                break
        if files:
            break
    assert files, 'no regular note available for private readback'
    p = files[0]
    try:
        fd = os.open(p, os.O_WRONLY | os.O_NOFOLLOW)
    except OSError as e:
        assert e.errno == errno.EROFS
    else:
        os.close(fd)
        raise RuntimeError('read-only boundary failed')
    vlt = subprocess.run(['vlt', 'vault=Personal', 'read', 'file=' + p.relative_to(root).as_posix()],
                         capture_output=True, timeout=30)
    assert vlt.returncode == 0 and vlt.stdout.rstrip(b'\n') == p.read_bytes().rstrip(b'\n'), 'private vlt readback failed (exit ' + str(vlt.returncode) + ')'
    print('PASS actual production read-only mount, private vlt readback, alternate host paths/profiles/sockets absent; no content output')
    print(json.dumps({'productionWrites': 'DISABLED', **tree_flags(root)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['read-check', 'status', 'snapshot', 'verify-snapshot'])
    parser.add_argument('--snapshot', type=Path, help='Existing private snapshot namespace (verify only)')
    args = parser.parse_args()
    try:
        if args.operation == 'read-check':
            read_check()
        elif args.operation == 'status':
            result = local_status()
            print(json.dumps(result, sort_keys=True))
            return 2 if result['writeGate'] == 'STOP' else 0
        elif args.operation == 'verify-snapshot':
            dest = args.snapshot
            root = Path('/home/johna/.local/state/hermes-native/vault-snapshots')
            if dest is None or dest.parent != root or not dest.name.startswith('snapshot-759-') or dest.resolve() != dest or root.resolve() != root:
                raise RuntimeError('snapshot namespace refused')
            for name in ['manifest.json', 'receipt.json']:
                p = dest / name
                s = p.lstat()
                if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o600:
                    raise RuntimeError('private snapshot metadata refused')
            expected = json.loads((dest / 'manifest.json').read_text())
            receipt = json.loads((dest / 'receipt.json').read_text())
            checksum = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
            if checksum != receipt['manifestSha256'] or manifest(dest / 'tree') != expected or manifest(dest / 'restore-disposable') != expected:
                raise RuntimeError('snapshot integrity changed: STOP')
            print(json.dumps({'integrity': 'PASS', 'disposableRestore': 'PASS', 'manifestSha256': checksum, 'productionRestore': 'NOT AUTHORIZED'}, sort_keys=True))
        else:
            # Operator-only; no public launcher route and no production restore.
            if args.snapshot is not None:
                raise RuntimeError('snapshot argument only valid for verification')
            status = local_status()
            if not status['localConvergence'] or not status['directPeerConvergence']:
                raise RuntimeError('snapshot requires observed convergence')
            root = Path('/home/johna/.local/state/hermes-native/vault-snapshots')
            for p in [root.parent, root]:
                if p.is_symlink():
                    raise RuntimeError('linked snapshot root refused')
                p.mkdir(mode=0o700, exist_ok=True)
                p.chmod(0o700)
            dest = Path(tempfile.mkdtemp(prefix='snapshot-759-', dir=root))
            dest.rmdir()  # exclusively created empty namespace; snapshot creates it
            result = snapshot(PRODUCTION, dest)
            print(json.dumps({'snapshot': str(dest), **result}, sort_keys=True))
    except Exception as error:
        print('FAIL vault safety: ' + type(error).__name__ + '; private diagnostics withheld', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
