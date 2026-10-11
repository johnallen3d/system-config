#!/usr/bin/env python3
"""#763 operational cold transfer/reverse mapping; never a staging promotion.

The NAS export command independently requires the source stopped and a managed
retirement receipt. Native import requires installed production metadata and an
exclusive closed namespace. No auth resolution/inference/polling occurs here.
Reverse plans retain complete latest native durable data and canonical auth;
NAS apply requires incident-specific approval and exact stopped-source CAS.
"""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import json
import os
import shlex
import contextlib
import fcntl
import stat
import math
import re
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

_spec = importlib.util.spec_from_file_location('production_state', Path(__file__).with_name('production-state.py'))
p = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(p)
require = p.require
NAS_ROOT = Path('/srv/appdata/hermes')
RETIREMENT = Path('/srv/appdata/hermes-native-cutover/retirement.json')
PRODUCTION_METADATA = Path('/home/johna/.config/hermes-native/production.json')
NAMESPACE = 'production/baseline-0.21.2'
LIVE_STATE = (*p.stage.STATE_FILES, 'channel_directory.json', 'gateway_state.json', 'gateway/telegram-offset.json')
CONTROL_FILES = ('config.yaml', 'cron/jobs.json', 'scripts/morning-brief.sh')
CREDENTIAL_TREES = ('gogcli/config', 'gogcli/data/keyring')
CREDENTIAL_FILES = ('gogcli/data/credentials.json', 'gogcli/data/credentials-personal.json', 'gogcli/config/credentials.json')
ARCHIVE_TREES = (*p.stage.QUARANTINE_TREES, *('skills/'+n for n in p.stage.PRIVATE_SKILLS))


def load(path):
    return json.loads(p.stage.read_private(path, owner=os.getuid()))


def native_metadata():
    # Home Manager owns this immutable metadata symlink; payload files never do.
    target = PRODUCTION_METADATA.resolve(strict=True)
    require(str(target).startswith('/nix/store/'), 'installed HM production metadata required')
    m = json.loads(target.read_bytes())
    require(m.get('schemaVersion') == 1 and m.get('namespace') == NAMESPACE
            and m.get('assetOwner') == 'system-config' and m.get('revision') == p.stage.REVISION
            and m.get('version') == p.stage.VERSION, 'production runtime identity')
    expected = {'state': '/home/johna/.local/state/hermes-native/production/baseline-0.21.2',
                'home': '/home/johna/.local/share/hermes-native/production/baseline-0.21.2/home',
                'config': '/home/johna/.config/hermes-native/production/baseline-0.21.2',
                'cache': '/home/johna/.cache/hermes-native/production/baseline-0.21.2'}
    require(m.get('paths') == expected, 'production roots mismatch; no staging promotion')
    for root in expected.values():
        p.stage.safe(Path(root), directory=True, owner=os.getuid())
    return m


def nas_stopped():
    r = subprocess.run(['docker', 'inspect', 'hermes'], capture_output=True, check=True)
    rows = json.loads(r.stdout); require(len(rows) == 1, 'exact source container')
    c = rows[0]
    require(c['State']['Running'] is False and c['State']['Pid'] == 0
            and c['HostConfig']['RestartPolicy']['Name'] == 'no'
            and c['Config']['Image'] == 'pi-cielo/hermes-agent:0.21.2-vault13', 'NAS stopped/restart gate')
    retirement = load(RETIREMENT)
    compose = Path('/opt/compose/hermes/docker-compose.yml')
    require(retirement.get('schemaVersion') == 1 and retirement.get('owner') == 'omarchy'
            and retirement.get('namespace') == NAMESPACE and retirement.get('phase') == 'SOURCE_STOPPED'
            and retirement.get('sourceRevision') == p.stage.REVISION and retirement.get('containerID') == c['Id']
            and retirement.get('stateRoot') == str(NAS_ROOT)
            and retirement.get('composeSha256') == p.stage.digest(p.stage.read_private(compose))
            and retirement.get('containerImageID') == c['Image'], 'managed NAS redeploy block identity')
    return c, retirement


KEYRING_LOCK = 'gogcli/data/keyring/.lock'


def keyring_lock_identity(path):
    p.stage.safe(path, owner=os.getuid())
    s = path.lstat()
    require(s.st_size == 0 and stat.S_IMODE(s.st_mode) == 0o600
            and s.st_gid == os.getgid(), 'canonical empty private keyring coordination inode required')
    return tuple(getattr(s, k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns',
                                        'st_mode','st_uid','st_gid','st_nlink'))


@contextlib.contextmanager
def inert_keyring_lock(root):
    """Keep the existing empty inode on NAS; refuse active flock/POSIX owners.

    Never create, truncate, replace or transport a lifecycle lock. Hold both
    advisory lock families for the whole cold read and verify inode/metadata CAS.
    No other descriptor reads/closes this inode while the POSIX lock is held.
    """
    path = root / KEYRING_LOCK
    p.stage.safe(path, missing=True, owner=os.getuid() if path.exists() else None)
    if not path.exists():
        yield {}
        require(not path.exists(), 'keyring coordination membership changed')
        return
    before = keyring_lock_identity(path)
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        require(tuple(getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns',
                                            'st_mode','st_uid','st_gid','st_nlink')) == before,
                'keyring coordination inode changed during open')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if sys.platform == 'linux':
            # Linux has separate families. Darwin unifies them; attempting both
            # there conflicts with our own flock, which already covers lockf.
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        signature = {'sha256': p.stage.digest(b''), 'mode': 0o600, 'mtime_ns': s.st_mtime_ns,
                     'uid': s.st_uid, 'gid': s.st_gid, 'device': s.st_dev, 'inode': s.st_ino,
                     'retainedOnSource': True, 'transported': False}
        yield {KEYRING_LOCK: signature}
        require(keyring_lock_identity(path) == before, 'keyring coordination inode drift')
        require(os.fstat(fd).st_size == 0, 'keyring coordination content drift')
    finally:
        # Closing this sole descriptor releases both lock families; the original
        # coordination inode and its zero bytes remain untouched.
        os.close(fd)


def pending_approval_record(name, raw):
    """Exact pinned tools.write_approval record; never authority to apply it."""
    parts=Path(name).parts
    v=json.loads(raw)
    require(len(parts)==3 and parts[0]=='pending' and parts[1] in {'memory','skills'}
            and isinstance(v,dict) and set(v)=={'id','subsystem','action','summary','origin','created_at','payload'}
            and v['subsystem']==parts[1] and isinstance(v['id'],str)
            and re.fullmatch('[0-9a-f]{8}',v['id']) is not None and parts[2]==v['id']+'.json'
            and v['origin'] in {'foreground','background_review'}
            and isinstance(v['payload'],dict) and isinstance(v['action'],str)
            and v['action']==v['payload'].get('action','') and isinstance(v['summary'],str)
            and type(v['created_at']) in {int,float} and math.isfinite(v['created_at'])
            and 0<v['created_at']<=time.time(), 'unknown pending/queued record requires review; no replay')
    return {'sha256':p.stage.digest(raw),'state':'UNAPPROVED','replay':'DISABLED','activeDiscovery':False}


def selected_names(root):
    """Known durable/auth/control inputs plus inert archive trees; no notes recursion."""
    names = set(p.DATABASES)
    required = {'SOUL.md', 'auth.json', 'config.yaml', 'cron/jobs.json'}
    candidates = set(LIVE_STATE) | set(CONTROL_FILES) | set(CREDENTIAL_FILES) | {'auth.json'}
    candidates |= {'.notebooklm/'+n for n in p.stage.NOTEBOOK_FILES}
    trees = (*CREDENTIAL_TREES, *ARCHIVE_TREES)
    shapes = {}
    for name in trees:
        d = root / name
        p.stage.safe(d, directory=True, missing=True, owner=os.getuid() if d.exists() else None)
        if not d.exists():
            shapes[name] = None; continue
        members = []
        for parent, dirs, files in os.walk(d, followlinks=False):
            for child in dirs:
                q = Path(parent)/child; p.stage.safe(q, directory=True, owner=os.getuid())
                members.append(str(q.relative_to(root))+'/')
            for child in files:
                q = Path(parent)/child; p.stage.safe(q, owner=os.getuid())
                relative = str(q.relative_to(root)); members.append(relative)
                if child.endswith('.lock') or child.startswith('.lock'):
                    require(relative == KEYRING_LOCK, 'lifecycle lock needs review')
                    keyring_lock_identity(q)
                    continue  # Proven inert inode remains on source, never replayed.
                candidates.add(relative)
        shapes[name] = sorted(members)
    for name in sorted(candidates):
        q = root / name
        p.stage.safe(q, missing=name not in required, owner=os.getuid() if q.exists() else None)
        if q.exists(): names.add(name)
    require(required.issubset(names), 'required final durable/control/auth inputs')
    pending=root/'pending'
    if pending.exists():
        for q in pending.rglob('*'):
            if q.is_dir():
                require(q.parent==pending and q.name in {'memory','skills'}, 'unknown pending directory requires review')
            else:
                name=q.relative_to(root).as_posix()
                pending_approval_record(name,p.stage.read_private(q,owner=os.getuid()))
    # Outbound messages are NOT human-approval history. Any such record remains
    # uncertain/actionable and blocks transfer; it is never labelled delivered.
    d=root/'pending_messages'
    require(not d.exists() or not any(d.iterdir()), 'actionable/uncertain queued files require review')
    return sorted(names), shapes


def cold_bundle(root, *, source_proof, secrets, exclusive_owner):
    require(exclusive_owner is True, 'exclusive stopped owner required')
    with inert_keyring_lock(root) as coordination:
        before, shapes = selected_names(root)
        data, receipt = p.checkpoint(root, before, exclusive_owner=exclusive_owner)
        after, shapes_after = selected_names(root)
        require(before == after and shapes == shapes_after, 'whole cold membership drift')
        receipt['inertCoordinationLocks'] = coordination
        approvals={n:pending_approval_record(n,b) for n,b in data.items() if n.startswith('pending/')}
        require(all(p.stage.digest(p.stage.read_private(root/n,owner=os.getuid()))==record['sha256']
                    for n,record in approvals.items()), 'pending approval archive moved during cold read')
        receipt['pendingApprovalArchives']=approvals
    # Preserve the full NAS source signature but transport ONLY canonical Codex
    # credentials. Other pools remain untouched on NAS, never in native archives.
    source_signatures = dict(receipt['files'])
    selected = p.stage.selected_auth(data['auth.json'])
    data['auth.json'] = selected
    receipt['files'] = {n: dict(s) for n, s in receipt['files'].items()}
    receipt['files']['auth.json']['sha256'] = p.stage.digest(selected)
    receipt['sourceFiles'] = source_signatures
    require(set(secrets) == {'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ALLOWED_USERS', 'TELEGRAM_HOME_CHANNEL', 'GOG_KEYRING_PASSWORD'}
            and all(isinstance(v, str) and v and not any(x in v for x in '\x00\r\n') for v in secrets.values()), 'canonical private channel/keyring inputs')
    return {'schemaVersion': 1, 'kind': 'HERMES763_COLD_PRODUCTION_TRANSFER',
            'namespace': NAMESPACE, 'receipt': receipt, 'sourceProof': source_proof,
            'files': {n: base64.b64encode(b).decode() for n, b in data.items()},
            'secrets': secrets, 'treeShapes': shapes}


def decode_bundle(bundle):
    require(bundle.get('schemaVersion') == 1 and bundle.get('kind') == 'HERMES763_COLD_PRODUCTION_TRANSFER'
            and bundle.get('namespace') == NAMESPACE, 'production transfer identity')
    require(isinstance(bundle.get('files'), dict) and len(bundle['files']) <= p.stage.MAX_ENTRIES,
            'production transfer members')
    data = {n: base64.b64decode(b, validate=True) for n, b in bundle['files'].items()}
    p.validate_checkpoint(data, bundle['receipt'])
    originals = bundle['receipt'].get('sourceFiles')
    require(isinstance(originals, dict) and set(originals) == set(data), 'original source signatures required')
    for n in data:
        if n != 'auth.json': require(originals[n] == bundle['receipt']['files'][n], 'non-auth source signature altered')
    approvals={n:pending_approval_record(n,b) for n,b in data.items() if n.startswith('pending/')}
    require(bundle['receipt'].get('pendingApprovalArchives',{})==approvals,
            'pending approvals must remain unapproved inert archives, never active or replayed')
    auth = json.loads(data['auth.json'])
    require(set(auth.get('providers', {})) == {'openai-codex'}
            and set(auth.get('credential_pool', {})) == {'openai-codex'}, 'nonselected credentials refused')
    return data


def production_config(data, state):
    c = p.stage.load_config(data['config.yaml'])
    require(isinstance(c, dict) and c.get('_config_version') == 44, 'production config schema')
    model = c.get('model', {})
    require(model.get('provider') == 'openai-codex'
            and model.get('base_url') == 'https://chatgpt.com/backend-api/codex', 'canonical model provider')
    c['terminal'] = {'backend': 'local', 'cwd': str(state/'workspace/notes')}
    # The installed gateway overrides terminal with the exact guarded adapter.
    # CLI, arbitrary file/edit/code tools, MCP and private-provider surfaces stay
    # unavailable. This config alone cannot arm or start the production owner.
    c['platform_toolsets'] = {'cli': [], 'telegram': ['terminal','skills','vision','memory']}
    c['mcp_servers'] = {}
    c['plugins'] = {'enabled': ['search', 'macros']}
    c['kanban'] = {**(c.get('kanban') or {}), 'dispatch_in_gateway': False, 'notify_in_gateway': False}
    telegram=dict(c.get('platforms',{}).get('telegram',{})); telegram['enabled']=True
    c['platforms']={'telegram':telegram}
    c.setdefault('cron',{})['provider']='builtin'
    c.setdefault('security', {})['redact_secrets'] = True
    return p.stage.encoded(c)


def transfer_plan(bundle, m):
    data = decode_bundle(bundle)
    normalized, checks = p.normalized_databases(data, bundle['receipt'])
    state, home, assets = Path(m['paths']['state']), Path(m['paths']['home']), Path(m['managedAssets'])
    state_plan = dict(normalized); home_plan = {}; mapping = {}
    for name in LIVE_STATE:
        if name in data:
            state_plan[name] = data[name]; mapping[name] = 'state/'+name
    for name in [*CREDENTIAL_FILES, *[n for n in data if any(n.startswith(t+'/') for t in CREDENTIAL_TREES)]]:
        if name in data:
            state_plan[name] = data[name]; mapping[name] = 'state/'+name
    for n in p.stage.NOTEBOOK_FILES:
        name = '.notebooklm/'+n
        require(name in data, 'NotebookLM minimal context required')
        home_plan[name] = data[name]; mapping[name] = 'home/'+name
    state_plan['auth.json'] = data['auth.json']; mapping['auth.json'] = 'state/auth.json'
    state_plan['config.yaml'] = production_config(data, state)
    state_plan['.secrets.json'] = p.stage.encoded(bundle['secrets'])
    # Original managed source code/schedule/private skills remain inert archives;
    # only explicitly reviewed Nix assets are copied to active discovery.
    for plugin in ('search', 'macros'):
        for leaf in ('plugin.yaml', '__init__.py'):
            rel = 'plugins/'+plugin+'/'+leaf
            code = p.stage.read_private(assets/rel)
            if leaf == '__init__.py':
                old = b'os.environ.get("HERMES_NATIVE_OFFLINE") != "1"'
                require(code.count(old) == 1, 'reviewed plugin adaptation anchor')
                code = code.replace(old, b'(os.environ.get("HERMES_NATIVE_STAGE") != "production" or os.environ.get("HERMES_NATIVE_READONLY") != "1")')
            state_plan[rel] = code
    # Public reviewed assets only. Retained private NAS skills remain outside
    # discovery; their existing individual production gates are not blanket grants.
    provenance=json.loads(p.stage.read_private(assets/'provenance.json'))
    for record in provenance['assets']:
        name=record['path']
        if name.startswith('skills/') and record['adoption']!='blocked-policy-drift':
            p.relative(name); state_plan[name]=p.stage.read_private(assets/name)
    # Gateway cron script routes to the separately sandboxed managed broker; it
    # never obtains a writable real-vault mount or invokes a workstation profile.
    state_plan['scripts/morning-brief.sh'] = ("#!/usr/bin/env bash\nset -euo pipefail\nexec "
        +shlex.quote(m.get('python',sys.executable))+" -I -B "
        +shlex.quote(str(assets/'production-runtime.py'))+" brief-request\n").encode()
    source_jobs = json.loads(data['cron/jobs.json'])
    jobs = source_jobs.get('jobs')
    require(isinstance(jobs, list) and len(jobs) == 1 and jobs[0].get('name') == 'pi-cielo-morning-brief',
            'exact single production scheduler mapping required')
    require(isinstance(jobs[0].get('id'),str) and jobs[0]['id'], 'retain authoritative scheduler identity')
    job = dict(jobs[0]); job.update(enabled=False, state='paused',
        paused_reason='Production import closed; controller arming required.', next_run_at=None,
        script='morning-brief.sh', no_agent=True, prompt='', workdir=str(state/'workspace/notes'), deliver=None, failure_deliver=None)
    state_plan['cron/jobs.json'] = p.stage.encoded({'jobs':[job]})
    return state_plan, home_plan, checks, mapping


def import_bundle(bundle, m):
    state, home = Path(m['paths']['state']), Path(m['paths']['home'])
    control = state/'controller'
    owner = load(control/'ownership.json')
    require(owner.get('owner') == 'nas' and owner.get('phase') == 'CLOSED', 'exclusive closed production import required')
    proof = bundle['sourceProof']
    require(proof.get('running') is False and proof.get('pid') == 0 and proof.get('restartPolicy') == 'no'
            and proof.get('managedRetirement') is True and proof.get('revision') == p.stage.REVISION
            and 0 <= time.time()-proof.get('observedAt', 0) <= 120, 'fresh coherent stopped-source proof')
    state_plan, home_plan, checks, mapping = transfer_plan(bundle, m)
    archives = control/'imports'; p.stage.mkdir(archives)
    bundle_hash = p.stage.digest(p.stage.encoded(bundle))
    evidence = archives/bundle_hash
    if evidence.exists():
        receipt = load(evidence/'receipt.json')
        require(receipt.get('sourceBundleSha256') == bundle_hash, 'repeat import receipt')
        for label, root in [('state',state),('home',home)]:
            require(all(p.signature(root/n) == s for n,s in receipt['files'][label].items()), 'repeat import target drift')
        return {'import':'PASS','changedFiles':0,'databases':7,'queueReplay':'DISABLED'}
    p.stage.mkdir(evidence)
    p.stage.atomic(evidence/'source-bundle.json', p.stage.encoded(bundle))
    before = {}
    for label, root, plan in [('state',state,state_plan),('home',home,home_plan)]:
        before[label] = {n:p.signature(root/n) if (root/n).exists() else None for n in plan}
        require(all(s is None for s in before[label].values()), 'unowned production payload preserved')
    changed = 0
    for label, root, plan in [('state',state,state_plan),('home',home,home_plan)]:
        e = evidence/label; p.stage.mkdir(e)
        changed += p.apply_cas(root,plan,before[label],restore_authorized=True,evidence=e)['changedFiles']
    receipt = {'schemaVersion':1,'kind':'HERMES763_PRODUCTION_IMPORT','namespace':NAMESPACE,
        'version':p.stage.VERSION,'revision':p.stage.REVISION,'sourceBundleSha256':bundle_hash,
        'sourceBundle':str(evidence/'source-bundle.json'),'databases':checks,'reverseMapping':mapping,
        'files':{'state':{n:p.signature(state/n) for n in state_plan},'home':{n:p.signature(home/n) for n in home_plan}},
        'queuePolicy':'PRESERVE_DELIVERED_NO_REPLAY_UNKNOWN_STOP','providerOwner':'native',
        'polling':'CLOSED','schedule':'CLOSED','vaultWrites':'CLOSED','retentionDaysMinimum':14}
    p.stage.atomic(evidence/'receipt.json',p.stage.encoded(receipt))
    p.stage.atomic(control/'import.json',p.stage.encoded(receipt))
    return {'import':'PASS','databases':7,'changedFiles':changed,'queueReplay':'DISABLED','gateway':'CLOSED'}


def reverse_mapping(original_bundle, incident_data, incident_receipt, current_nas, raw_nas_auth):
    original = decode_bundle(original_bundle)
    require(current_nas == original_bundle['receipt']['sourceFiles'], 'NAS source branch diverged; manual review required')
    p.validate_checkpoint(incident_data,incident_receipt)
    normalized, checks = p.normalized_databases(incident_data,incident_receipt)
    plan = dict(normalized)
    for name in LIVE_STATE:
        if name in original:
            require(name in incident_data, 'incident durable routing/memory member lost')
            plan[name] = incident_data[name]
    # Preserve unrelated NAS-only credentials while mapping latest native rotating
    # Codex provider/pool back. Source raw auth never leaves NAS during forward
    # transfer; the operator reads it only under exact stopped-source CAS here.
    require(p.stage.digest(raw_nas_auth) == current_nas['auth.json']['sha256'], 'NAS auth CAS')
    baseline, latest = json.loads(raw_nas_auth), json.loads(p.stage.selected_auth(incident_data['auth.json']))
    baseline.setdefault('providers',{})['openai-codex'] = latest['providers']['openai-codex']
    baseline.setdefault('credential_pool',{})['openai-codex'] = latest['credential_pool']['openai-codex']
    baseline['active_provider'] = 'openai-codex'
    if 'updated_at' in latest: baseline['updated_at'] = latest['updated_at']
    plan['auth.json'] = p.stage.encoded(baseline)
    for n in incident_data:
        if n.startswith(('gogcli/config/','gogcli/data/keyring/')) or n in CREDENTIAL_FILES or n.startswith('.notebooklm/'):
            plan[n] = incident_data[n]
    # Source generated config, code and schedule remain original NAS versions;
    # reverse-mapping them from native would point NAS at Nix/native-only paths.
    require(all(not n.startswith(('plugins/','scripts/','skills/')) and n not in CONTROL_FILES for n in plan),
            'reverse generated-code/config mapping refused')
    return plan, checks


def merged_reverse_auth(raw_nas_auth, latest_native_auth, expected):
    require(p.signature(expected[0]) == expected[1], 'NAS auth CAS')
    baseline, latest = json.loads(raw_nas_auth), json.loads(p.stage.selected_auth(latest_native_auth))
    baseline.setdefault('providers', {})['openai-codex'] = latest['providers']['openai-codex']
    baseline.setdefault('credential_pool', {})['openai-codex'] = latest['credential_pool']['openai-codex']
    baseline['active_provider'] = 'openai-codex'
    if 'updated_at' in latest:
        baseline['updated_at'] = latest['updated_at']
    return p.stage.encoded(baseline)


def reverse_schedule(source_raw, native_raw, next_run):
    """Retain source code/routes and one job identity; reconcile runtime cursors."""
    source=json.loads(source_raw); native=json.loads(native_raw)
    require(set(source)==set(native)=={'jobs'} and len(source['jobs'])==len(native['jobs'])==1,
            'one exact reverse scheduler mapping')
    original,current=source['jobs'][0],native['jobs'][0]
    require(original.get('id')==current.get('id') and isinstance(original.get('id'),str)
            and original.get('name')==current.get('name')=='pi-cielo-morning-brief'
            and original.get('schedule')==current.get('schedule')
            and original.get('schedule') in ({'kind':'cron','expr':'0 5 * * *'},
                                             {'kind':'cron','expr':'0 5 * * *','display':'0 5 * * *'}),
            'scheduler identity/history must not fork on reverse')
    when=datetime.fromisoformat(next_run)
    local=when.astimezone(ZoneInfo('America/New_York'))
    require(when.tzinfo is not None and (local.hour,local.minute,local.second)==(5,0,0)
            and 0<when.timestamp()-time.time()<=48*3600,'fresh future NY cursor; never replay stopped/uncertain slot')
    job=dict(original)
    for key in ['last_run_at','last_status','last_error','last_delivery_error','failure_streak']:
        if key in current: job[key]=current[key]
    if current.get('repeat'):
        require(isinstance(current['repeat'],dict) and isinstance(original.get('repeat'),dict)
                and current['repeat'].get('times')==original['repeat'].get('times')
                and current['repeat'].get('times') in {None,0},'only original unbounded daily repetition')
        job['repeat']={**original['repeat'],'completed':current['repeat'].get('completed',0)}
    # A killed run's delivery is uncertain, not authority to retry it. Preserve
    # its durable execution history while scheduling only a future slot.
    for key in ['fire_claim','run_claim','pending_slot','manual_run_at','manual_run_prompt']:
        job.pop(key,None)
    job.update(next_run_at=next_run,state='scheduled',paused_reason=None)
    return p.stage.encoded({'jobs':[job]})


def native_stopped(m=None):
    m = native_metadata() if m is None else m
    owner = load(Path(m['paths']['state'])/'controller/ownership.json')
    require(owner.get('schemaVersion') == 1 and owner.get('namespace') == NAMESPACE
            and owner.get('phase') == 'STOPPED_REVIEW_REQUIRED'
            and all(owner.get(k) == 'DISABLED' for k in ('poller','scheduler','vaultWrites','providerRefresh')),
            'native ownership must be revoked before incident recovery')
    r = subprocess.run(['/usr/bin/systemctl','--user','show','hermes-production.service',
                        '--property=ActiveState','--property=MainPID'], capture_output=True, check=True,
                       env={'PATH':'/usr/bin:/bin','LANG':'C','XDG_RUNTIME_DIR':'/run/user/1000',
                            'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/1000/bus'})
    rows = dict(line.split('=',1) for line in r.stdout.decode().splitlines() if '=' in line)
    require(rows.get('ActiveState') in {'inactive','failed'} and rows.get('MainPID') == '0', 'native service must be stopped')
    return {'observedAt':time.time(),'activeState':rows['ActiveState'],'mainPID':0,
            'ownershipPhase':'STOPPED_REVIEW_REQUIRED'}


def incident_export(m):
    state, home = Path(m['paths']['state']), Path(m['paths']['home'])
    proof = native_stopped(m)
    original_receipt = load(state/'controller/import.json')
    original_bundle = load(Path(original_receipt['sourceBundle']))
    # State snapshot and independent HOME auth payload are protected by the same
    # host-local runtime lock; all service/writer entrypoints use this inode.
    spec = importlib.util.spec_from_file_location('production_writers',Path(__file__).with_name('production-writers.py'))
    w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
    with w.held_lock(state/'controller/runtime.lock'):
        names, _ = selected_names(state)
        data, receipt = p.checkpoint(state,names,exclusive_owner=True)
        before = {n:p.signature(home/('.notebooklm/'+n)) for n in p.stage.NOTEBOOK_FILES}
        for name in p.stage.NOTEBOOK_FILES:
            rel = '.notebooklm/'+name
            data[rel] = p.stage.read_private(home/rel,owner=os.getuid())
            receipt['files'][rel] = before[name]
        normalized, checks = p.normalized_databases(data,receipt)
        require(before == {n:p.signature(home/('.notebooklm/'+n)) for n in p.stage.NOTEBOOK_FILES}, 'incident HOME drift')
        native_stopped(m)
        # Persist the entire raw incident first, including WALs and generated
        # control/scheduler state; only the exact durable path map is applied.
        artifact = {'schemaVersion':1,'kind':'HERMES763_NATIVE_INCIDENT','namespace':NAMESPACE,
            'receipt':receipt,'files':{n:base64.b64encode(b).decode() for n,b in data.items()},'nativeStopped':proof}
        sha = p.stage.digest(p.stage.encoded(artifact))
        evidence = state/'controller/incidents'/sha
        p.stage.mkdir(evidence)
        p.stage.atomic(evidence/'incident.json',p.stage.encoded(artifact))
        plan = dict(normalized)
        for n in data:
            if (n in LIVE_STATE or n in CREDENTIAL_FILES or n == 'auth.json'
                    or n.startswith(('gogcli/config/','gogcli/data/keyring/','.notebooklm/'))):
                plan[n] = data[n]
        plan['auth.json'] = p.stage.selected_auth(plan['auth.json'])
        from cron.jobs import compute_next_run
        job=json.loads(data['cron/jobs.json'])['jobs'][0]
        now=datetime.now(ZoneInfo('America/New_York')); anchor=now
        brief=state/'controller/acceptance-brief.json'
        if brief.exists():
            recorded=load(brief)
            if recorded.get('status') in {'CLAIMED','DONE'} and any(
                    name=='journal/'+now.date().isoformat()+'.md' for name in recorded.get('files',[])):
                anchor=max(now,now.replace(hour=5,minute=0,second=0,microsecond=0))
        next_run=compute_next_run(job['schedule'],anchor.isoformat())
        require(next_run,'pinned reverse scheduler cursor')
        existing=job.get('next_run_at')
        if existing and datetime.fromisoformat(existing)>datetime.fromisoformat(next_run): next_run=existing
        plan['cron/jobs.json']=reverse_schedule(decode_bundle(original_bundle)['cron/jobs.json'],data['cron/jobs.json'],next_run)
        result = {'schemaVersion':1,'kind':'HERMES763_REVERSE_APPLY','namespace':NAMESPACE,
            'sourceBundleSha256':original_receipt['sourceBundleSha256'],'incidentSha256':sha,
            'originalSourceFiles':original_bundle['receipt']['sourceFiles'],
            'nativeStopped':proof,'incidentArtifact':artifact,'checks':checks,
            'files':{n:base64.b64encode(b).decode() for n,b in plan.items()}}
        p.stage.atomic(evidence/'reverse-payload.json',p.stage.encoded(result))
        return result


def apply_reverse(payload, root, evidence, approval, *, current_native_proof=None):
    require(payload.get('schemaVersion') == 1 and payload.get('kind') == 'HERMES763_REVERSE_APPLY'
            and payload.get('namespace') == NAMESPACE, 'reverse identity')
    require(approval.get('kind') == 'JOHN_INCIDENT_RESTORE'
            and approval.get('action') == 'RESTORE_NAS_RUNTIME_STATE_NOT_VAULT'
            and approval.get('namespace') == NAMESPACE and approval.get('confirmedBy') == 'John Allen'
            and approval.get('incidentSha256') == payload.get('incidentSha256')
            and approval.get('sourceBundleSha256') == payload.get('sourceBundleSha256')
            and approval.get('reversePayloadSha256') == p.stage.digest(p.stage.encoded(payload))
            and approval.get('approvedAt',0) <= time.time() < approval.get('expiresAt',0)
            and 0 < approval['expiresAt']-approval['approvedAt'] <= 600, 'incident-specific John restore approval required')
    require(p.stage.digest(p.stage.encoded(payload['incidentArtifact'])) == payload['incidentSha256'], 'incident artifact binding')
    incident = payload['incidentArtifact']
    data = {n:base64.b64decode(b,validate=True) for n,b in incident['files'].items()}
    p.validate_checkpoint(data,incident['receipt'])
    # Approval binds the retained incident/payload, not a fabricated refreshed
    # timestamp. The real operator separately obtains a NEW stopped-native proof
    # immediately before apply, so waiting for John never rewrites approved bytes.
    snapshot=payload['nativeStopped']; proof=current_native_proof if current_native_proof is not None else snapshot
    require(snapshot.get('mainPID') == 0 and snapshot.get('ownershipPhase') == 'STOPPED_REVIEW_REQUIRED'
            and snapshot.get('activeState') in {'inactive','failed'}
            and proof.get('mainPID') == 0 and proof.get('ownershipPhase') == 'STOPPED_REVIEW_REQUIRED'
            and proof.get('activeState') in {'inactive','failed'}
            and 0 <= time.time()-proof.get('observedAt',0) <= 120,
            'fresh stopped-native proof required')
    plan = {n:base64.b64decode(b,validate=True) for n,b in payload['files'].items()}
    require({*p.DATABASES,'cron/jobs.json'}.issubset(plan) and set(payload['checks']) == set(p.DATABASES)
            and sum(map(len,plan.values())) <= p.MAX_TOTAL, 'validated complete reverse data required')
    for n in plan:
        p.relative(n)
        require(n in p.DATABASES or n in LIVE_STATE or n in {'auth.json','cron/jobs.json'} or n in CREDENTIAL_FILES
                or n.startswith(('gogcli/config/','gogcli/data/keyring/','.notebooklm/')), 'reverse path not durable data')
        if n=='cron/jobs.json':
            require(n in data,'retained native scheduler artifact required')
            next_run=json.loads(plan[n])['jobs'][0]['next_run_at']
            require(plan[n]==reverse_schedule(p.stage.read_private(root/n,owner=os.getuid()),data[n],next_run),
                    'reverse only original source routes plus exact native cursor/outcome')
        elif n not in p.DATABASES:
            require(n in data and plan[n] == (p.stage.selected_auth(data[n]) if n == 'auth.json' else data[n]), 'incident mapping mismatch')
    expected_all = payload['originalSourceFiles']
    done = evidence/'receipt.json'
    if done.exists():
        receipt = load(done)
        require(receipt.get('incidentSha256') == payload['incidentSha256']
                and all((p.signature(root/n) if (root/n).exists() else None) == s for n,s in receipt['files'].items()),
                'repeat reverse target drift')
        return {'reverse':'PASS','changedFiles':0,'gateway':'CLOSED'}
    current_names, _ = selected_names(root)
    _, current = p.checkpoint(root,current_names,exclusive_owner=True)
    require(current['files'] == expected_all, 'NAS branch diverged; manual reconciliation required')
    plan['auth.json'] = merged_reverse_auth(p.stage.read_private(root/'auth.json'),plan['auth.json'],(root/'auth.json',expected_all['auth.json']))
    deletions = [n for n in expected_all if any(n == db+s for db in p.DATABASES for s in ('-wal','-shm'))]
    p.stage.mkdir(evidence)
    p.stage.atomic(evidence/'reverse-payload.json',p.stage.encoded(payload))
    p.stage.atomic(evidence/'approval.json',p.stage.encoded(approval))
    p.stage.atomic(evidence/'status.json',p.stage.encoded({'status':'INCOMPLETE','incidentSha256':payload['incidentSha256']}))
    # Preserve old source WAL/SHM bytes BEFORE replacing any database. Retained
    # journals stay outside NAS state; a crash cannot authorize source restart.
    for n in deletions:
        p.stage.atomic(evidence/'sidecar-preimages'/n,p.stage.read_private(root/n,owner=os.getuid()))
    expected = {n:p.signature(root/n) if (root/n).exists() else None for n in plan}
    apply_evidence = evidence/'apply'; p.stage.mkdir(apply_evidence)
    result = p.apply_cas(root,plan,expected,restore_authorized=True,evidence=apply_evidence)
    for n in deletions:
        require(p.signature(root/n) == expected_all[n], 'source sidecar CAS drift')
        (root/n).unlink()
        fd = os.open((root/n).parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    files = {n:p.signature(root/n) for n in plan}
    files.update({n:None for n in deletions})
    p.stage.atomic(done,p.stage.encoded({'schemaVersion':1,'incidentSha256':payload['incidentSha256'],
        'sourceBundleSha256':payload['sourceBundleSha256'],'files':files,'gateway':'CLOSED','providerOwner':'NAS_STOPPED'}))
    p.stage.atomic(evidence/'status.json',p.stage.encoded({'status':'COMPLETE','incidentSha256':payload['incidentSha256']}))
    return {'reverse':'PASS','changedFiles':result['changedFiles'],'gateway':'CLOSED'}


@contextlib.contextmanager
def source_operation_lock():
    # EXACT same local inode as pi-cielo's NAS prevention/stop/resume guard.
    # No distributed reservation or service. Cold bytes/reverse CAS cannot race
    # another managed source mutation while each independently rechecks stopped.
    path=RETIREMENT.parent/'operation.lock'
    p.stage.safe(path.parent,directory=True,owner=os.getuid())
    p.stage.safe(path,missing=True,owner=os.getuid() if path.exists() else None)
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        expected=os.fstat(fd); current=path.stat()
        require((expected.st_dev,expected.st_ino)==(current.st_dev,current.st_ino),'source operation lock replaced')
        yield
        current=path.stat()
        require((expected.st_dev,expected.st_ino)==(current.st_dev,current.st_ino),'source operation lock replaced')
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)


def main():
    require(len(sys.argv)==2, 'fixed production transfer operation required')
    operation=sys.argv[1]
    if operation in {'cold-export','reverse-apply'}:
        require(os.getuid()==1000,'NAS source owner')
        with source_operation_lock(): _main_locked(operation)
    else: _main_locked(operation)


def _main_locked(operation):
    if operation == 'cold-export':
        require(os.getuid()==1000, 'NAS source owner')
        c, retirement = nas_stopped()
        env = dict(v.split('=',1) for v in c['Config']['Env'] if '=' in v)
        secrets = {n:env.get(n,'') for n in ('TELEGRAM_BOT_TOKEN','TELEGRAM_ALLOWED_USERS','TELEGRAM_HOME_CHANNEL')}
        # Existing approved Doppler notes/prd secret arrives over private stdin;
        # never reuse executable staging state or copy a workstation profile.
        provision_raw = sys.stdin.buffer.read(4097)
        require(len(provision_raw) <= 4096, 'bounded canonical provisioning')
        provision = json.loads(provision_raw)
        require(set(provision) == {'GOG_KEYRING_PASSWORD'}, 'canonical Calendar provisioning only')
        secrets.update(provision)
        proof = {'running':False,'pid':0,'restartPolicy':'no','managedRetirement':True,
            'revision':p.stage.REVISION,'observedAt':time.time(),'imageID':c['Image'],'containerID':c['Id'],
            'retirementSha256':p.stage.digest(p.stage.encoded(retirement))}
        bundle = cold_bundle(NAS_ROOT,source_proof=proof,secrets=secrets,exclusive_owner=True)
        # Private pipe ONLY: never invoke this exporter without a private sink.
        sys.stdout.buffer.write(p.stage.encoded(bundle))
    elif operation == 'import':
        raw = sys.stdin.buffer.read(p.MAX_TOTAL*2+1)
        require(len(raw)<=p.MAX_TOTAL*2, 'bounded transfer stream')
        print(json.dumps(import_bundle(json.loads(raw),native_metadata()),sort_keys=True))
    elif operation == 'reverse-apply':
        require(os.getuid()==1000, 'NAS source owner')
        nas_stopped()
        raw = sys.stdin.buffer.read(p.MAX_TOTAL*3+1)
        require(len(raw)<=p.MAX_TOTAL*3, 'bounded private reverse stream')
        packet = json.loads(raw)
        require(set(packet) == {'payload','approval','nativeStopped'}, 'exact recovery packet with fresh actual native proof')
        payload = packet['payload']
        sha = payload.get('incidentSha256','')
        require(len(sha)==64 and all(c in '0123456789abcdef' for c in sha), 'incident identity')
        evidence = RETIREMENT.parent/'recovery'/sha
        result = apply_reverse(payload,NAS_ROOT,evidence,packet['approval'],current_native_proof=packet['nativeStopped'])
        nas_stopped()
        print(json.dumps(result,sort_keys=True))
    else:
        raise ValueError('unsupported transfer operation; no implicit restore')


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError,subprocess.SubprocessError) as e:
        print('REFUSED production transfer: '+type(e).__name__,file=sys.stderr)
        raise SystemExit(64)
