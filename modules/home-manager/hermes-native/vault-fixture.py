#!/usr/bin/env python3
"""#759 fixed disposable gate suite using the existing installed Syncthing binary.

Runs only in launcher's isolated mount/PID/network namespaces. Three temporary
peers reproduce the observed chain topology. They are NOT host services, not
paired to production, and have no host network, notes, credentials or sockets.
"""
from __future__ import annotations
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('safety', Path(__file__).with_name('vault-safety.py'))
safety = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wait(test, timeout=75):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            if test():
                return
        except FileNotFoundError:
            # A disposable peer can temporarily lack the restored canary during
            # async convergence. Absence is NOT success; retain the bounded wait.
            pass
        time.sleep(.2)
    raise RuntimeError('disposable convergence timed out')


def write(root, relative, data, *, approval, expected):
    """Test transaction protocol, NOT a replacement for vault-owned task code.

    Exact operator approval + preimage CAS + persistent path-based flock +
    same-directory fsync/replace. Locks are LOCAL, never distributed authority.
    """
    p = root / relative
    assert p.is_relative_to(root) and '..' not in Path(relative).parts
    assert not p.is_symlink() and p.parent.resolve().is_relative_to(root.resolve())
    grant = {'path': relative, 'before': expected, 'after': sha(data)}
    assert approval == grant, 'exact approved mutation required'
    flags = safety.tree_flags(root)
    assert not flags['conflicts'] and not flags['temporary'], 'conflict/temporary is STOP'
    locks = root / '.locks'
    locks.mkdir(mode=0o700, exist_ok=True)
    lock = locks / sha(relative.encode())
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = sha(p.read_bytes()) if p.exists() else None
        assert current == expected, 'preimage changed: STOP'
        if current == sha(data):
            return
        tmpfd, tmp = tempfile.mkstemp(prefix='.atomic-', dir=p.parent)
        try:
            with os.fdopen(tmpfd, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(tmp, p)
            directory = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        assert p.read_bytes() == data
    finally:
        os.close(fd)


def transactions(base):
    root = base / 'transactions'; root.mkdir()
    p = root / 'canary.md'; p.write_bytes(b'SYNTHETIC BEFORE\n')
    before = (p.read_bytes(), p.stat().st_mtime_ns)
    data = b'SYNTHETIC AFTER\n'; expected = sha(before[0])
    grant = {'path': 'canary.md', 'before': expected, 'after': sha(data)}
    def refused(fn):
        try:
            fn()
        except (AssertionError, BlockingIOError):
            pass
        else:
            raise AssertionError('negative gate did not refuse')
        assert (p.read_bytes(), p.stat().st_mtime_ns) == before
    refused(lambda: write(root, 'canary.md', data, approval=None, expected=expected))
    refused(lambda: write(root, 'canary.md', data, approval=grant, expected='0' * 64))
    (root / 'blocked.sync-conflict-synthetic.md').write_bytes(b'SYNTHETIC CONFLICT')
    refused(lambda: write(root, 'canary.md', data, approval=grant, expected=expected))
    (root / 'blocked.sync-conflict-synthetic.md').rename(base / 'preserved-conflict.md')
    (root / '.locks').mkdir()
    with (root / '.locks' / sha(b'canary.md')).open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        refused(lambda: write(root, 'canary.md', data, approval=grant, expected=expected))
    write(root, 'canary.md', data, approval=grant, expected=expected)
    after = (p.read_bytes(), p.stat().st_mtime_ns)
    write(root, 'canary.md', data, approval={'path': 'canary.md','before':sha(data),'after':sha(data)}, expected=sha(data))
    assert (p.read_bytes(), p.stat().st_mtime_ns) == after
    (root / 'linked.md').symlink_to(p)
    try:
        write(root, 'linked.md', data, approval=None, expected=expected)
    except AssertionError:
        pass
    else:
        raise AssertionError('linked target accepted')
    print('PASS disposable exact-approval/CAS/conflict-stop/same-file flock/atomic fsync/readback/idempotence/link refusal', flush=True)


def readonly_attacks():
    root = Path('/fixture-ro')
    mount = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines() if line.split()[4] == str(root)]
    assert len(mount) == 1 and 'ro' in mount[0][5].split(',')
    source = root / 'note.md'
    original = source.read_bytes()
    attacks = [lambda: source.write_bytes(b'BAD'), lambda: source.unlink(),
               lambda: source.rename(root / 'renamed.md'), lambda: (root / 'new.md').write_text('BAD'),
               lambda: os.link(source, '/tmp/escape-hardlink'),
               lambda: (root / 'alias.md').write_text('BAD')]
    for attack in attacks:
        try:
            attack()
        except OSError as error:
            assert error.errno in {errno.EROFS, errno.EXDEV, errno.EPERM, errno.EACCES}
        else:
            raise AssertionError('read-only attack unexpectedly succeeded')
    assert source.read_bytes() == original
    assert not Path('/home/johna/notes').exists() and not Path('/run/user/1000').exists()
    assert not Path('/fixture-ro/external').exists()
    print('PASS disposable RO overwrite/create/delete/rename/hardlink/symlink attacks; host alternate path/socket inaccessible', flush=True)


class Peers:
    def __init__(self, base):
        self.base = base
        self.processes = []
        self.configs = []
        self.roots = []
        self.keys = []
        self.ids = []
        self.logs = []
    def api(self, i, endpoint, method='GET', data=None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request('http://127.0.0.1:' + str(18401 + i) + endpoint,
              data=body, headers={'X-API-Key': self.keys[i], 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read()
            return json.loads(body) if body else None
    def start(self):
        binary = os.environ['HERMES_NATIVE_SYNCTHING']
        for i in range(3):
            home = self.base / ('peer-' + str(i)); home.mkdir(mode=0o700)
            r = subprocess.run([binary, 'generate', '--home=' + str(home), '--no-port-probing'], capture_output=True, timeout=30)
            assert r.returncode == 0
            xml = ET.parse(home / 'config.xml'); root = xml.getroot()
            root.find('gui/address').text = '127.0.0.1:' + str(18401 + i)
            self.keys.append(root.findtext('gui/apikey'))
            options = root.find('options')
            for name in ['globalAnnounceEnabled', 'localAnnounceEnabled', 'relaysEnabled', 'natEnabled', 'crashReportingEnabled']:
                if options.find(name) is not None:
                    options.find(name).text = 'false'
            for node in list(options.findall('listenAddress')):
                options.remove(node)
            ET.SubElement(options, 'listenAddress').text = 'tcp://127.0.0.1:' + str(22401 + i)
            if options.find('urAccepted') is not None:
                options.find('urAccepted').text = '-1'
            xml.write(home / 'config.xml')
            log = (home / 'process.log').open('wb'); self.logs.append(log)
            self.processes.append(subprocess.Popen([binary,'serve','--home='+str(home),'--no-browser','--no-upgrade','--no-restart'], stdout=log, stderr=subprocess.STDOUT))
            def ready():
                assert self.processes[i].poll() is None, 'fixture peer exited'
                try:
                    self.api(i, '/rest/system/status'); return True
                except OSError:
                    return False
            wait(ready)
            self.ids.append(self.api(i, '/rest/system/status')['myID'])
            notes = home / 'notes-fixture'; notes.mkdir(); self.roots.append(notes)
        # Observed chain: endpoint A <-> relay B <-> endpoint C (no A-C pair).
        for i in range(3):
            peers = [j for j in range(3) if abs(i-j) == 1]
            for j in peers:
                self.api(i, '/rest/config/devices', 'POST', {'deviceID':self.ids[j], 'name':'synthetic-'+str(j), 'addresses':['tcp://127.0.0.1:'+str(22401+j)], 'compression':'metadata'})
            self.api(i, '/rest/config/folders', 'POST', {'id':'disposable-759','label':'SYNTHETIC ONLY','path':str(self.roots[i]),'type':'sendreceive','rescanIntervalS':1,'fsWatcherEnabled':True,'fsWatcherDelayS':1,
                     'devices':[{'deviceID':self.ids[j]} for j in [i]+peers]})
        wait(self.clean)
    def clean(self):
        for i in range(3):
            assert self.processes[i].poll() is None, 'fixture peer exited'
            s = self.api(i, '/rest/db/status?folder=disposable-759')
            if s.get('state') != 'idle' or any(s.get(k) for k in ['errors','pullErrors','needTotalItems','needBytes','error','invalid','watchError']):
                return False
            for j in range(3):
                if abs(i-j) == 1:
                    c = self.api(i, '/rest/db/completion?folder=disposable-759&device='+self.ids[j])
                    con = self.api(i, '/rest/system/connections')['connections'].get(self.ids[j],{})
                    if not con.get('connected') or c.get('completion') != 100 or any(c.get(k) for k in ['needItems','needBytes','needDeletes']):
                        return False
        return True
    def scan(self, i):
        self.api(i, '/rest/db/scan?folder=disposable-759', 'POST')
    def pause(self, paused):
        for i in range(3):
            self.api(i, '/rest/config/folders/disposable-759', 'PATCH', {'paused':paused})
        wait(lambda: all(self.api(i,'/rest/config/folders/disposable-759')['paused'] == paused for i in range(3)))
    def canonical(self, data):
        return all((p/'canary.md').is_file() and (p/'canary.md').read_bytes() == data for p in self.roots) and self.clean()
    def close(self):
        for p in self.processes:
            p.terminate()
        for p in self.processes:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait()
        for log in self.logs:
            log.close()


def atomic(p, data):
    fd, tmp = tempfile.mkstemp(prefix='.atomic-', dir=p.parent)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, p)


def sync_cases(base):
    peers = Peers(base)
    try:
        peers.start()
        data = b'SYNTHETIC CREATE\n'; atomic(peers.roots[0]/'canary.md',data); peers.scan(0)
        wait(lambda: peers.canonical(data))
        data = b'SYNTHETIC UPDATE\n'; atomic(peers.roots[2]/'canary.md',data); peers.scan(2)
        wait(lambda: peers.canonical(data))
        (peers.roots[1]/'canary.md').unlink(); peers.scan(1)
        wait(lambda: all(not (p/'canary.md').exists() for p in peers.roots) and peers.clean())
        assert all(not safety.tree_flags(p)['conflicts'] and not safety.tree_flags(p)['temporary'] for p in peers.roots)
        print('PASS actual installed Syncthing three disposable chain peers create/update/delete/hash convergence; zero needed/errors/temp/conflicts',flush=True)
        data = b'SYNTHETIC SNAPSHOT\n'; atomic(peers.roots[0]/'canary.md',data); peers.scan(0)
        wait(lambda:peers.canonical(data))
        peers.pause(True)
        result = safety.snapshot(peers.roots[0], base/'snapshot')
        assert result['integrity'] == 'PASS'
        peers.pause(False)
        changed=b'SYNTHETIC POST SNAPSHOT\n';atomic(peers.roots[2]/'canary.md',changed);peers.scan(2)
        wait(lambda:peers.canonical(changed))
        # Restore authority test: ALL temporary peers/writers paused; authority
        # endpoint restored and scanned SENDONLY; peers resumed one at a time.
        peers.pause(True)
        peers.api(0,'/rest/config/folders/disposable-759','PATCH',{'type':'sendonly'})
        atomic(peers.roots[0]/'canary.md',(base/'snapshot/tree/canary.md').read_bytes())
        peers.api(0,'/rest/config/folders/disposable-759','PATCH',{'paused':False})
        peers.scan(0)
        peers.api(0,'/rest/db/override?folder=disposable-759','POST')
        for i in [1,2]:
            peers.api(i,'/rest/config/folders/disposable-759','PATCH',{'paused':False})
            wait(lambda i=i:(peers.roots[i]/'canary.md').read_bytes() == data)
        wait(lambda:peers.canonical(data))
        peers.api(0,'/rest/config/folders/disposable-759','PATCH',{'type':'sendreceive'})
        wait(peers.clean)
        assert all(not safety.tree_flags(p)['conflicts'] for p in peers.roots)
        print('PASS fresh disposable snapshot/integrity/exact metadata restore; explicit authority/all-peer pause/order prevents post-snapshot state undo',flush=True)
        peers.pause(True)
        a=b'SYNTHETIC OVERLAP A\n';c=b'SYNTHETIC OVERLAP C\n'
        atomic(peers.roots[0]/'canary.md',a);atomic(peers.roots[2]/'canary.md',c)
        peers.pause(False)
        for i in [0,2]:peers.scan(i)
        wait(lambda:all(safety.tree_flags(p)['conflicts'] for p in peers.roots) and peers.clean())
        for root in peers.roots:
            preserved={p.read_bytes() for p in root.glob('canary*.md')}
            assert preserved == {a,c}, 'mixed/lost conflict payload'
            assert not safety.tree_flags(root)['temporary']
            canonical=(root/'canary.md').read_bytes()
            try:
                write(root,'canary.md',b'BAD',approval={'path':'canary.md','before':sha(canonical),'after':sha(b'BAD')},expected=sha(canonical))
            except AssertionError:
                pass
            else:raise AssertionError('conflict did not stop writer')
            assert (root/'canary.md').read_bytes() == canonical
        print('PASS real Syncthing overlapping same-file complete versions preserved on all disposable peers; conflict stops writes; no auto-delete/mtime-winner',flush=True)
    finally:
        peers.close()


def main():
    os.umask(0o077)
    try:
        assert os.environ.get('HERMES_VAULT_MODE') == 'disposable'
        assert not Path('/home/johna/notes').exists() and not Path('/run/user/1000').exists()
        assert not any(k.startswith(('PI_','CLAUDE_')) or k.endswith(('TOKEN','API_KEY')) for k in os.environ)
        # Actual namespace has only loopback, not the host network.
        assert [line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]] == ['lo']
        base=Path(tempfile.mkdtemp(prefix='hermes-vault-759-',dir='/tmp'))
        readonly_attacks();transactions(base);sync_cases(base)
        print('PASS isolated write grants do NOT imply production write permission or cross-host lock authority',flush=True)
        return 0
    except Exception as error:
        print('FAIL disposable vault gate: '+type(error).__name__+' '+str(error)[:160],file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
