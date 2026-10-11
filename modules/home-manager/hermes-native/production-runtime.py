#!/usr/bin/env python3
"""#763 distinct production controller; CLOSED until receipt-backed cutover.

One foreground HM supervisor, sealed pinned gateway, exact reviewed task broker
and fixed operator routes. No network listener, observer transport, profile copy,
staging promotion, implicit unlock, automatic NAS resume or vault restore.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import re
import tempfile
import stat
import shutil
import shlex
import socket
import threading
import signal
import struct
import urllib.request
import base64
import contextlib
import fcntl
from datetime import date, datetime
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location('production_transfer',Path(__file__).with_name('production-transfer.py'))
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
p = t.p


def initialize(m):
    state, home = Path(m['paths']['state']), Path(m['paths']['home'])
    for relative in ('controller','workspace','logs','cron','scripts','plugins','memories','sessions'):
        p.stage.mkdir(state/relative)
    for root in (Path(m['paths']['config']),Path(m['paths']['cache']),home):
        p.stage.safe(root,directory=True,owner=os.getuid())
    owner = state/'controller/ownership.json'
    initial = {'schemaVersion':1,'namespace':t.NAMESPACE,'owner':'nas','phase':'CLOSED',
               'poller':'DISABLED','scheduler':'DISABLED','vaultWrites':'DISABLED','providerRefresh':'DISABLED'}
    if not owner.exists():
        p.stage.atomic(owner,p.stage.encoded(initial))
    else:
        current = t.load(owner)
        p.require(current.get('schemaVersion') == 1 and current.get('namespace') == t.NAMESPACE,
                  'ownership receipt identity; preserve unknown state')
    # Stable inode, never unlink/reset existing locks/journals/receipts on activation.
    for name in ('runtime.lock','transition.lock','writer.lock'):
        parent = state/'controller' if name != 'writer.lock' else state
        path = parent/name
        p.stage.safe(path,missing=True,owner=os.getuid() if path.exists() else None)
        fd = os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        os.close(fd)
    return {'namespace':t.NAMESPACE,'initialized':'PASS','gateway':'CLOSED','providerRefresh':'CLOSED'}


def check(m):
    state = Path(m['paths']['state'])
    owner = t.load(state/'controller/ownership.json')
    closed = owner.get('phase') == 'CLOSED' and owner.get('owner') == 'nas'
    revoked = owner.get('phase') == 'STOPPED_REVIEW_REQUIRED' and owner.get('owner') == 'native'
    p.require(owner.get('namespace') == t.NAMESPACE and (closed or revoked)
              and all(owner.get(k) == 'DISABLED' for k in
                      ('poller','scheduler','vaultWrites','providerRefresh')),
              'closed production ownership required; revoked native is engineering-only')
    p.require(m.get('gatewayEnabled') is False and m.get('productionWrites') == 'CLOSED'
              and m.get('morningBrief') == 'CLOSED', 'installed closed runtime identity')
    r = subprocess.run(['/usr/bin/systemctl','--user','show',m['service'],'--property=ActiveState',
                        '--property=MainPID','--property=RefuseManualStart','--property=Restart'],
                       capture_output=True,check=True,
                       env={'PATH':'/usr/bin:/bin','LANG':'C','XDG_RUNTIME_DIR':'/run/user/1000',
                            'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/1000/bus'})
    row = dict(line.split('=',1) for line in r.stdout.decode().splitlines() if '=' in line)
    p.require(row.get('ActiveState') in ({'inactive','failed'} if revoked else {'inactive'})
              and row.get('MainPID') == '0' and row.get('Restart') == 'no'
              and (revoked or row.get('RefuseManualStart') == 'yes'), 'actual closed production unit')
    if revoked and row.get('RefuseManualStart') != 'yes':
        override=Path('/run/user/1000/systemd/user/hermes-production.service.d/763-cutover.conf')
        p.require(p.stage.read_private(override,owner=os.getuid()) == b'[Unit]\nRefuseManualStart=false\n',
                  'only retained exact initial cutover override; no new manual-start authority')
    return {'namespace':t.NAMESPACE,'installedUnit':'PASS','gateway':'CLOSED','scheduler':'CLOSED',
            'vaultWrites':'CLOSED','providerRefresh':'CLOSED','productionReady':False}


def writer_module():
    spec = importlib.util.spec_from_file_location('production_writers',Path(__file__).with_name('production-writers.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def task_targets(task, args, today=None):
    """Fixed deterministic authorities and exact content paths, never shell text."""
    p.require(isinstance(task,str) and isinstance(args,(list,tuple)) and len(args)<=64
              and all(isinstance(a,str) and len(a)<=32768 and '\x00' not in a for a in args), 'bounded task argv')
    today = today or datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    def option(name, default=None):
        p.require(args.count(name)<=1, 'duplicate writer option')
        if name not in args: return default
        i=args.index(name); p.require(i+1<len(args), 'writer option value required')
        return args[i+1]
    when=option('--date',today)
    p.require(re.fullmatch(r'\d{4}-\d{2}-\d{2}',when) and date.fromisoformat(when).isoformat()==when,'valid target date')
    daily='journal/'+when+'.md'
    if task=='write-food-log':
        p.require('--date' in args and all(option(k) is not None for k in ['--meal','--food','--amount','--unit']),
                  'explicit food date/meal/food/amount/unit required')
        return (daily,)
    if task in {'activity-log','adjust-food-log'}: return (daily,)
    if task=='log-weight':
        p.require(len(args)==1 and re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',args[0]),'one numeric weight required')
        return ('journal/'+today+'.md',)
    if task=='morning-brief':
        p.require(not args,'fixed morning brief; no additional arguments')
        return ('journal/'+today+'.md',)
    if task=='add-list-item':
        positional=[]; i=0
        while i<len(args):
            if args[i] in {'--date','--time'}:
                p.require(i+1<len(args),'list option value required'); i+=2
            else:
                p.require(not args[i].startswith('-'),'unknown list option'); positional.append(args[i]); i+=1
        p.require(1<=len(positional)<=2 and positional[0].strip(),'one literal list item')
        kind=positional[1] if len(positional)==2 else 'tasks'
        p.require(kind in {'daily','tasks','shopping','groceries'},'one exact approved list')
        # Existing task treats --date as a reminder tag, not a future journal
        # destination. Its daily-path helper always selects today's NY journal.
        return ('journal/'+today+'.md' if kind=='daily' else 'lists/'+kind+'.md',)
    if task=='common-foods-browser':
        p.require(not args,'fixed browser generation')
        return ('health/common-foods-browser.html',)
    if task in {'recipe-table','save-recipe'}:
        p.require(args and args[0].startswith('recipes/') and args[0].endswith('.md'),'exact canonical recipe required')
        p.relative(args[0]); p.require(not any(q.startswith('.') for q in Path(args[0]).parts),'hidden recipe refused')
        if task=='recipe-table':
            p.require(len(args)==3 and args[1]=='--plan-file' and args[2].startswith('recipes/') and args[2].endswith('.json'),
                      'explicit existing renderer plan required; no Pi/model fallback')
            p.relative(args[2]); p.require(not any(q.startswith('.') for q in Path(args[2]).parts),'hidden plan refused')
        else:
            p.require(len(args)==3, 'canonical Markdown plus explicit renderer plan JSON required')
        return (args[0],)
    if task=='save-common-food':
        p.require(len(args)==1, 'one explicit reusable food JSON record required')
        return ('health/common-foods.yaml','health/common-foods-browser.html')
    raise ValueError('unreviewed writer/task authority; no generic shell or fallback')


def canonical_overlay(task, args, run):
    """Two exact canonical note/data adapters; never generic filesystem editing."""
    if task=='save-recipe':
        note,raw_markdown,raw_plan=args
        markdown=json.loads(raw_markdown)
        p.require(isinstance(markdown,str) and markdown and len(markdown.encode())<=32768
                  and re.search(r'^## Ingredients\s*$',markdown,re.M)
                  and re.search(r'^## (?:Steps|Instructions|Method)\s*$',markdown,re.M),
                  'canonical recipe ingredient/step sections required')
        plan=json.loads(raw_plan)
        p.require(isinstance(plan,dict) and set(plan)=={'row_order','columns'}
                  and isinstance(plan['row_order'],list) and isinstance(plan['columns'],list)
                  and 0<len(plan['columns'])<=8,'explicit bounded recipe renderer plan; no model subprocess')
        p.stage.atomic(run/'overlays'/note,markdown.encode())
        p.stage.atomic(run/'recipe-plan.json',p.stage.encoded(plan))
        return
    p.require(task=='save-common-food','fixed canonical adapter')
    import math
    import yaml
    food=json.loads(args[0])
    p.require(isinstance(food,dict) and set(food)<={'id','name','aliases','category','serving','nutrition','recipe','notes','source'}
              and {'id','name','serving','nutrition'}<=set(food), 'explicit canonical food record fields')
    p.require(isinstance(food['id'],str) and re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,100}',food['id'])
              and isinstance(food['name'],str) and 0<len(food['name'])<=256, 'stable food identity/name')
    for key in ['notes','source','category']:
        p.require(key not in food or isinstance(food[key],str) and len(food[key])<=4096, 'literal bounded food metadata')
    aliases=food.get('aliases',[])
    p.require(isinstance(aliases,list) and len(aliases)<=32
              and all(isinstance(q,str) and 0<len(q)<=256 for q in aliases), 'literal food aliases')
    if 'recipe' in food:
        p.require(isinstance(food['recipe'],str) and food['recipe'].startswith('recipes/') and food['recipe'].endswith('.md'),
                  'exact canonical recipe reference')
        p.relative(food['recipe']); p.require(not any(q.startswith('.') for q in Path(food['recipe']).parts),'hidden recipe refused')
    serving=food['serving']; nutrition=food['nutrition']
    p.require(isinstance(serving,dict) and set(serving)<={'amount','unit','label'} and {'amount','unit'}<=set(serving)
              and isinstance(serving['amount'],(int,float)) and not isinstance(serving['amount'],bool)
              and math.isfinite(serving['amount']) and serving['amount']>0
              and isinstance(serving['unit'],str) and 0<len(serving['unit'])<=64
              and ('label' not in serving or isinstance(serving['label'],str) and len(serving['label'])<=256),
              'explicit positive food serving amount/unit')
    p.require(isinstance(nutrition,dict) and set(nutrition)<={'calories','protein_g','carbs_g','fat_g','fiber_g','sodium_mg','sugar_g'}
              and {'calories','protein_g','carbs_g','fat_g'}<=set(nutrition)
              and all(isinstance(q,(int,float)) and not isinstance(q,bool) and math.isfinite(q) and q>=0 for q in nutrition.values()),
              'explicit finite nonnegative reusable nutrition')
    path=run/'overlays/health/common-foods.yaml'
    current=yaml.safe_load(p.stage.read_private(path))
    p.require(isinstance(current,dict) and isinstance(current.get('foods'),list)
              and all(isinstance(q,dict) and isinstance(q.get('id'),str) for q in current['foods'])
              and len({q['id'] for q in current['foods']})==len(current['foods']), 'valid existing canonical foods; no reset')
    matches=[i for i,q in enumerate(current['foods']) if q['id']==food['id']]
    if matches:
        old=current['foods'][matches[0]]
        current['foods'][matches[0]]={**old,**food,
            'serving':{**(old.get('serving') or {}),**serving},
            'nutrition':{**(old.get('nutrition') or {}),**nutrition}}
    else: current['foods'].append(food)
    p.stage.atomic(path,yaml.safe_dump(current,sort_keys=False,allow_unicode=True).encode())


def sandboxed_task(m, task, args, *, scope=None, observer, scan, today=None):
    """Run a reviewed writer on retained private overlays, then exact CAS commit.

    Gateway, brief and operator task adapters all call this one implementation.
    Real vault is RO in the child; only disposable target copies are writable.
    No profile, source auth, bot token, executable import or generic command is
    mounted. The parent's one shared inode spans helper private-/tmp namespaces.
    """
    w=writer_module(); state=Path(m['paths']['state']); vault=Path(m['vault'])
    files=task_targets(task,args,today)
    owner=t.load(state/'controller/ownership.json')
    p.require(owner.get('namespace')==t.NAMESPACE and owner.get('owner')=='native'
              and owner.get('phase') in {'NATIVE_ARMED','NATIVE_LIVE'} and owner.get('vaultWrites')=='ENABLED',
              'actual native writer ownership required')
    if scope is None:
        p.require(owner['phase']=='NATIVE_LIVE','maintenance acceptance must use fresh timed exclusion')
    ledger=t.load(state/'controller/task-code.json')
    p.require(ledger.get('kind')=='REVIEWED_USER_OWNED_VAULT_TASK_CODE'
              and ledger.get('namespace')==t.NAMESPACE,'reviewed user-owned task ledger required')
    dependencies={'.mise/tasks/lib-vlt-note.sh','.mise/tasks/vault-note-rmw.py','.mise/tasks/daily-path',
                  '.mise/tasks/strip-journal-leading-blank-line'}
    if task=='morning-brief': dependencies.update({'.mise/tasks/get-weather','.mise/tasks/get-calendar'})
    if task=='save-recipe': dependencies.add('.mise/tasks/recipe-table')
    if task=='save-common-food': dependencies.update({'.mise/tasks/common-food','.mise/tasks/common-foods-browser'})
    p.require(dependencies.issubset(ledger.get('files',{})),'complete reviewed helper dependencies required')
    for name,sha in ledger.get('files',{}).items():
        p.relative(name); p.require(name.startswith(('.mise/tasks/','scripts/')),'only reviewed task code in ledger')
        p.require(p.stage.digest(p.stage.read_private(vault/name,owner=os.getuid()))==sha,'task code changed; preserve and review it')
    command= [m['environment']['HERMES_NATIVE_MISE'],'run',task,'--',*args]
    if task=='adjust-food-log':
        command=[m['python'],'-I','-B',str(Path(m['managedAssets'])/'skills/health/food/scripts/adjust-food-log'),*args]
    elif task=='save-recipe':
        command=[m['environment']['HERMES_NATIVE_MISE'],'run','recipe-table','--',args[0],
                 '--force','--plan-file','/tmp/recipe-plan.json']
    elif task=='save-common-food':
        command=[m['environment']['HERMES_NATIVE_MISE'],'run','common-foods-browser']
    else:
        p.require('.mise/tasks/'+task in ledger['files'],'writer authority missing from reviewed code ledger')
    # Each private run is retained, even on refusal. Its bytes are never auto-restored.
    runs=state/'controller/task-runs'; p.stage.mkdir(runs)
    run=Path(tempfile.mkdtemp(prefix='task-',dir=runs)); run.chmod(0o700)
    guard=w.normal_reserve(state,vault,files,observer=observer) if scope is None else w.reserve(state,vault,files,scope=scope,observer=observer)
    with guard as reservation:
        environment=dict(m['environment'])
        environment={k:v for k,v in environment.items() if not k.startswith(('PI_','CLAUDE_'))
                     and not k.endswith(('TOKEN','API_KEY')) and not k.startswith('HERMES_PRODUCTION_')}
        environment.update(HOME='/tmp/task-home',XDG_CONFIG_HOME='/tmp/task-config',XDG_CACHE_HOME='/tmp/task-cache',
                           XDG_DATA_HOME='/tmp/task-data',XDG_STATE_HOME='/tmp/task-state',
                           HERMES_NATIVE_STAGE='production',HERMES_NATIVE_READONLY='0',HERMES_PRODUCTION_WRITER_HELD='1',
                           MORNING_BRIEF_DELIVERY='stdout',MORNING_BRIEF_INCLUDE_FLIGHTS='0',VAULT_NAME='Personal')
        alias=str(state/'workspace/notes')
        environment.update(VAULT_DIR=alias,VLT_VAULT_PATH=alias,MISE_TRUSTED_CONFIG_PATHS=alias)
        argv=[m['bubblewrap'],'--unshare-all','--die-with-parent','--new-session',
              '--ro-bind','/nix/store','/nix/store','--proc','/proc','--dev','/dev','--tmpfs','/dev/shm',
              '--tmpfs','/tmp','--tmpfs','/home','--dir','/etc','--dir','/usr','--dir','/usr/bin','--dir','/bin',
              '--symlink',m['envBinary'],'/usr/bin/env','--symlink',m['bashBinary'],'/bin/bash',
              '--symlink',m['bashBinary'],'/bin/sh','--ro-bind',str(vault),'/vault-source','--tmpfs',alias]
        # A disposable root permits vlt's .vlt.lock/index without changing the
        # real vault. Every existing content/code entry is individually RO.
        for entry in sorted(vault.iterdir()):
            # Agent-profile instructions are not inputs to deterministic tasks.
            # CLAUDE.md is a normal vault symlink to AGENTS.md; leave it untouched
            # and outside the child, rather than relaxing safe() for symlinks.
            if entry.name == 'CLAUDE.md':
                continue
            p.stage.safe(entry,directory=entry.is_dir(),owner=os.getuid())
            if entry.name not in {'.vlt.lock','.vlt','.obsidian'}:
                argv+=['--ro-bind',str(entry),alias+'/'+entry.name]
        google_original=None
        if task=='morning-brief':
            # Read-only Calendar API + public weather. Gog still needs a writable
            # coordination inode/cache. As in the existing provider doctor, give
            # it a private disposable copy, NEVER writable canonical credentials.
            # No Telegram token or Codex grant enters this deterministic child.
            google_source=state/'gogcli'; p.stage.safe(google_source,directory=True,owner=os.getuid())
            google_original={q.relative_to(google_source).as_posix():p.signature(q)
                             for q in sorted(google_source.rglob('*')) if q.is_file()}
            p.require(all(not q.is_symlink() for q in google_source.rglob('*')),'canonical Google copy without symlinks')
            google_copy=run/'calendar-gogcli'; p.stage.mkdir(google_copy)
            for name,signature in google_original.items():
                if name=='data/keyring/.lock':
                    continue  # Original coordination inode is never transported or changed.
                p.stage.atomic(google_copy/name,p.stage.read_private(google_source/name,owner=os.getuid()))
                p.require(p.stage.digest(p.stage.read_private(google_copy/name))==signature['sha256'],'Google private-copy CAS')
            secret=t.load(state/'.secrets.json')['GOG_KEYRING_PASSWORD']
            environment.update(GOG_HOME=str(google_source),GOG_KEYRING_PASSWORD=secret,GOG_READONLY='1')
            argv+=['--share-net','--ro-bind','/etc/resolv.conf','/etc/resolv.conf',
                   '--bind',str(google_copy),str(google_source)]
        parents=sorted({str(Path(n).parent) for n in files})
        originals={}
        # vlt integrity/index bookkeeping is disposable, never a second real-vault
        # writer. Keep original metadata RO but let vlt create its private index.
        index=run/'obsidian'; p.stage.mkdir(index)
        if (vault/'.obsidian/app.json').exists():
            p.stage.atomic(index/'app.json',p.stage.read_private(vault/'.obsidian/app.json',owner=os.getuid()))
        else: p.stage.atomic(index/'app.json',b'{}\n')
        argv+=['--bind',str(index),alias+'/.obsidian']
        for parent in parents:
            real=vault/parent; p.stage.safe(real,directory=True,owner=os.getuid())
            overlay=run/'overlays'/parent; p.stage.mkdir(overlay)
            selected={Path(n).name for n in files if str(Path(n).parent)==parent}
            original_names={q.name for q in real.iterdir()}; originals[parent]=original_names
            for q in real.iterdir():
                p.stage.safe(q,directory=q.is_dir(),owner=os.getuid())
                if q.name in selected:
                    p.require(q.is_file(),'regular target required')
                    p.stage.atomic(overlay/q.name,p.stage.read_private(q,owner=os.getuid()))
            argv+=['--bind',str(overlay),alias+'/'+parent]
            # Siblings remain readable RO, but cannot be renamed/unlinked/edited.
            for q in sorted(real.iterdir()):
                if q.name not in selected:
                    stub=overlay/q.name
                    if q.is_dir(): p.stage.mkdir(stub)
                    else: p.stage.atomic(stub,b'')
                    argv+=['--ro-bind',str(q),alias+'/'+parent+'/'+q.name]
        if task in {'save-recipe','save-common-food'}:
            canonical_overlay(task,args,run)
        if task=='save-recipe':
            argv+=['--ro-bind',str(run/'recipe-plan.json'),'/tmp/recipe-plan.json']
        reservation.check()
        if task=='save-common-food':
            validation=subprocess.run([*argv,'--chdir',alias,m['environment']['HERMES_NATIVE_MISE'],
                                       'run','common-food','--','validate'],
                                      env=environment,capture_output=True,timeout=30,cwd='/')
            p.stage.atomic(run/'validation.stdout',validation.stdout)
            p.stage.atomic(run/'validation.stderr',validation.stderr)
            p.require(validation.returncode==0,'canonical food validation failed; no live commit')
            reservation.check()
        result=subprocess.run([*argv,'--chdir',alias,*command],env=environment,capture_output=True,timeout=180,cwd='/')
        p.stage.atomic(run/'stdout',result.stdout); p.stage.atomic(run/'stderr',result.stderr)
        if google_original is not None:
            p.require(google_original=={q.relative_to(google_source).as_posix():p.signature(q)
                                        for q in sorted(google_source.rglob('*')) if q.is_file()},
                      'canonical Google context moved during read-only brief; no credential overwrite')
        p.require(result.returncode==0,'reviewed task failed; retained private branch, no real-vault commit')
        plan={}
        for name in files:
            output=run/'overlays'/name
            p.stage.safe(output,owner=os.getuid())
            data=p.stage.read_private(output,owner=os.getuid())
            p.require(len(data)<=4*1024*1024,'bounded task postimage')
            plan[name]=data
        # bwrap mounted non-target siblings exist only inside the child. Any new
        # physical scratch entry must be one of the exact requested postimages.
        for parent in parents:
            overlay=run/'overlays'/parent
            selected={Path(n).name for n in files if str(Path(n).parent)==parent}
            expected_names=originals[parent]|selected
            p.require({q.name for q in overlay.iterdir()}<=expected_names,'unexpected task output; retain private branch')
            for q in overlay.iterdir():
                if q.name not in selected:
                    p.require((q.is_file() and q.stat().st_size==0) or (q.is_dir() and not any(q.iterdir())),
                              'non-target sibling overlay changed')
        reservation.check()
        for name,data in plan.items():
            if reservation.expected[name] is None or p.stage.digest(data)!=reservation.expected[name]['sha256']:
                p.atomic_durable(vault/name,data,reservation.expected[name])
        final=w.manifest(vault,files)
        p.require(all(final[n]['sha256']==p.stage.digest(plan[n]) for n in files),'exact task postimage readback')
        scan(files)
        reservation.complete(final)
        p.stage.atomic(run/'receipt.json',p.stage.encoded({'status':'COMPLETE','files':final,
                       'retentionDaysMinimum':14,'realVaultInChild':'READ_ONLY','provider':'NO_MODEL',
                       'delivery':'STDOUT_ONLY','policy':'TIMED_MAINTENANCE' if scope is not None else 'NAS_NORMAL_POLICY'}))
        return result.stdout


def local_writer_callbacks(m):
    spec=importlib.util.spec_from_file_location('vault_safety',Path(__file__).with_name('vault-safety.py'))
    v=importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
    p.require(str(v.PRODUCTION)==m['vault'],'actual existing local notes root')
    waiting=False
    def scan(names):
        nonlocal waiting
        v.scan_content(names); waiting=True
    def observe(names):
        nonlocal waiting
        deadline=time.monotonic()+60
        while True:
            row=v.local_status()
            p.require(not row['conflicts'] and not row['temporary'] and not row['special'],
                      'conflict/temporary/special content; stop writers and retain branches')
            if row['localConvergence'] and row['directPeerConvergence']:
                waiting=False; return row
            p.require(waiting and time.monotonic()<deadline,'local/direct convergence required')
            time.sleep(.2)
    return observe,scan


def read_task(m, task, args):
    """No generic shell, profile mount, provider credentials or writable content."""
    state=Path(m['paths']['state']); vault=Path(m['vault']); alias=str(state/'workspace/notes')
    p.require(isinstance(args,list) and len(args)<=32 and all(isinstance(a,str) and len(a)<=8192 for a in args),'bounded read argv')
    if task=='date':
        p.require(not args or args in [['+%F'],['+%Y-%m-%d'],['+%Y-%m-%d %H:%M:%S %Z (%z)']],
                  'fixed NY date/time read')
        now=datetime.now(ZoneInfo('America/New_York'))
        return (now.strftime(args[0][1:] if args else '%Y-%m-%d')+'\n').encode()
    if task=='vlt':
        p.require(len(args)==3 and args[:2]==['vault=Personal','read'] and args[2].startswith('file='),'vlt read only')
        name=args[2][5:]; p.relative(name)
        p.require(not any(q.startswith('.') for q in Path(name).parts),'no hidden/config reads')
        p.stage.safe(vault/name,owner=os.getuid())
        # Exact local note bytes; no vlt write/cache/acknowledge operation.
        return p.stage.read_private(vault/name,owner=os.getuid())
    allowed={'common-food','macros','macros-details'}
    p.require(task in allowed,'unreviewed read command')
    if task=='common-food': p.require(args and args[0] in {'search','show','validate'},'common-food read only')
    ledger=t.load(state/'controller/task-code.json')
    for name in ['.mise/tasks/'+task,*(['scripts/'+task] if task in {'macros','macros-details'} else [])]:
        p.require(name in ledger['files'] and p.stage.digest(p.stage.read_private(vault/name,owner=os.getuid()))==ledger['files'][name],
                  'reviewed read task code unchanged')
    env=dict(m['environment']); env.update(HOME='/tmp/read-home',XDG_CONFIG_HOME='/tmp/read-config',
        XDG_CACHE_HOME='/tmp/read-cache',HERMES_NATIVE_READONLY='1',HERMES_NATIVE_STAGE='production',
        VAULT_DIR=alias,VLT_VAULT_PATH=alias,MISE_TRUSTED_CONFIG_PATHS=alias)
    env={k:v for k,v in env.items() if not k.startswith(('PI_','CLAUDE_','HERMES_PRODUCTION_')) and not k.endswith(('TOKEN','API_KEY'))}
    command=[m['bubblewrap'],'--unshare-all','--die-with-parent','--new-session','--ro-bind','/nix/store','/nix/store',
        '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--tmpfs','/home','--dir','/etc','--dir','/usr','--dir','/usr/bin',
        '--dir','/bin','--symlink',m['envBinary'],'/usr/bin/env','--symlink',m['bashBinary'],'/bin/bash',
        '--symlink',m['bashBinary'],'/bin/sh','--ro-bind',str(vault),alias,'--chdir',alias,
        m['environment']['HERMES_NATIVE_MISE'],'run',task,'--',*args]
    result=subprocess.run(command,env=env,capture_output=True,timeout=30,cwd='/')
    p.require(result.returncode==0 and len(result.stdout)<=65536,'read task failed/bounded result; private diagnostics withheld')
    return result.stdout


WRITE_TASKS={'write-food-log','activity-log','log-weight','add-list-item','recipe-table','common-foods-browser','adjust-food-log',
             'save-recipe','save-common-food'}


def terminal_request(arguments):
    """Parse model argv, never evaluate shell substitutions/operators or env assignments."""
    p.require(isinstance(arguments,dict) and isinstance(arguments.get('command'),str),'terminal command required')
    p.require(not any(arguments.get(k) for k in ['background','pty','force','workdir','notify_on_complete','watch_patterns']),
              'no general execution/background/environment override')
    command=arguments['command']
    p.require(len(command)<=32768 and not any(x in command for x in ['\x00','\n','\r','`']), 'bounded literal command')
    argv=shlex.split(command)
    p.require(argv and not any(q in {';','&&','||','|','>','>>','<','&'} for q in argv),'single literal command; no shell operators')
    if argv[0]=='date': return {'operation':'read','task':'date','args':argv[1:]}
    if argv[0]=='vlt': return {'operation':'read','task':'vlt','args':argv[1:]}
    if argv[:2]==['mise','run']:
        p.require(len(argv)>=3,'named reviewed task required')
        task=argv[2]; args=argv[3:]
        if args[:1]==['--']: args=args[1:]
        if task in WRITE_TASKS:
            task_targets(task,args); return {'operation':'write','task':task,'args':args}
        p.require(task in {'common-food','macros','macros-details'},'named read authority required')
        return {'operation':'read','task':task,'args':args}
    # The approved food skill's helper is a fixed Nix asset, not arbitrary Python.
    if len(argv)>=4 and argv[0] in {'python3','python'} and argv[1]=='-I' and argv[2].endswith('/skills/health/food/scripts/adjust-food-log'):
        task_targets('adjust-food-log',argv[3:]); return {'operation':'write','task':'adjust-food-log','args':argv[3:]}
    raise ValueError('general terminal/shell/script authority is not exposed')


def broker_frame(connection, value=None):
    """One private inherited socketpair, not a listener/service/auth surface."""
    limit=1024*1024
    if value is not None:
        data=p.stage.encoded(value); p.require(len(data)<=limit,'bounded broker frame')
        connection.sendall(struct.pack('!I',len(data))+data); return
    def receive(count):
        data=b''
        while len(data)<count:
            part=connection.recv(count-len(data))
            if not part: raise EOFError('private gateway child exited')
            data+=part
        return data
    size=struct.unpack('!I',receive(4))[0]; p.require(0<size<=limit,'bounded broker frame')
    return json.loads(receive(size))


def live_owner(m, capability):
    owner=t.load(Path(m['paths']['state'])/'controller/ownership.json')
    p.require(owner.get('schemaVersion')==1 and owner.get('namespace')==t.NAMESPACE and owner.get('owner')=='native'
              and owner.get('phase') in {'NATIVE_ARMED','NATIVE_LIVE'} and owner.get(capability)=='ENABLED',
              'exclusive native ownership/capability required')
    return owner


def revoke(m):
    path=Path(m['paths']['state'])/'controller/ownership.json'; expected=p.signature(path); owner=t.load(path)
    p.require(owner.get('namespace')==t.NAMESPACE and owner.get('owner')=='native','native ownership required')
    owner.update(phase='STOPPED_REVIEW_REQUIRED',poller='DISABLED',scheduler='DISABLED',vaultWrites='DISABLED',
                 providerRefresh='DISABLED',revokedAt=time.time())
    p.atomic_durable(path,p.stage.encoded(owner),expected)


@contextlib.contextmanager
def scheduler_transition(m):
    """Same stable inode across parent and RO-controller child; never unlink it."""
    path=Path(m['paths']['state'])/'controller/transition.lock'
    p.stage.safe(path,owner=os.getuid())
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        writer_module().verify_binding(path,fd)
        yield
        writer_module().verify_binding(path,fd)
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN); os.close(fd)


def gateway_child(m):
    """Pinned gateway in sealed OS namespace; supported registry and auth hooks."""
    state=Path(m['paths']['state']); home=Path(m['paths']['home'])
    p.require(not Path('/home/johna/.codex').exists() and not Path('/home/johna/.config/claude-personal').exists(),
              'workstation profile boundary')
    owner=live_owner(m,'poller'); live_owner(m,'providerRefresh')
    connection=socket.socket(fileno=int(os.environ['HERMES_PRODUCTION_BROKER_FD']))
    lock=threading.Lock()
    def request(value):
        with lock:
            broker_frame(connection,value); response=broker_frame(connection)
        p.require(response.get('status')=='OK','guarded adapter refused; no fallback')
        return response['output']
    install_gateway_hooks(m,request)
    from gateway.run import main as upstream_main
    sys.argv=['hermes-native-production-gateway']
    upstream_main()


def install_provider_hook(m):
    state=Path(m['paths']['state'])
    # Supported canonical resolver, not custom token rotation. The complete
    # singleton/pool live ONLY at this namespace; CLI/profile fallback is absent
    # in the mount namespace. Supported write-through consequently stays native.
    import hermes_cli.auth_codex as codex
    original_resolver=codex.resolve_codex_runtime_credentials
    def exclusive_resolver(**kwargs):
        live_owner(m,'providerRefresh')
        auth=t.load(state/'auth.json')
        p.require(auth.get('active_provider')=='openai-codex' and set(auth.get('providers',{}))=={'openai-codex'},
                  'canonical native-only grant; no CLI fallback')
        result=original_resolver(**kwargs)
        live_owner(m,'providerRefresh')
        return result
    codex.resolve_codex_runtime_credentials=exclusive_resolver


PUBLIC_PROBE_PROMPT = 'Reply with exactly HERMES_NATIVE_OK. This is a public connectivity test.'


def public_probe_child(m):
    """One supported canonical Codex request, no agent/tools/history/context."""
    acceptance_context(m)
    p.require(not Path('/home/johna/.codex').exists(), 'no workstation credential fallback')
    install_provider_hook(m)
    from hermes_cli.auth_codex import resolve_codex_runtime_credentials
    from agent.auxiliary_client import _create_openai_client, CodexAuxiliaryClient
    state = Path(m['paths']['state'])
    model_config = p.stage.load_config(p.stage.read_private(state/'config.yaml'))['model']
    model = model_config.get('default') or model_config.get('model')
    p.require(model_config.get('provider') == 'openai-codex'
              and isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9._-]{1,100}', model),
              'existing configured canonical Codex model required; no default/fallback')
    credentials = resolve_codex_runtime_credentials()
    p.require(credentials.get('provider') == 'openai-codex'
              and credentials.get('source') == 'hermes-auth-store'
              and credentials.get('base_url') == 'https://chatgpt.com/backend-api/codex',
              'supported canonical native singleton only')
    client = CodexAuxiliaryClient(_create_openai_client(api_key=credentials['api_key'],
        base_url=credentials['base_url'], max_retries=0, timeout=25), model)
    try:
        answer = client.chat.completions.create(model=model,
            messages=[{'role': 'user', 'content': PUBLIC_PROBE_PROMPT}], timeout=25)
        text = answer.choices[0].message.content
        p.require(isinstance(text, str) and text.strip() == 'HERMES_NATIVE_OK',
                  'one tiny public probe exact response required; no retry')
        acceptance_context(m)
        sys.stdout.buffer.write(b'HERMES_NATIVE_OK\n')
    finally:
        client.close()


def public_probe(m, *, run=None):
    """Durable one-shot probe BEFORE gateway start, protected by runtime.lock."""
    state = Path(m['paths']['state'])
    with writer_module().held_lock(state/'controller/runtime.lock'), scheduler_transition(m):
        owner, arming = acceptance_context(m)
        row = dict(q.split('=', 1) for q in systemctl('show', m['service'],
                   '-p', 'ActiveState', '-p', 'MainPID').decode().splitlines() if '=' in q)
        p.require(row.get('ActiveState') == 'inactive' and row.get('MainPID') == '0',
                  'public probe only before sole gateway start; no concurrent provider user')
        path = state/'controller/acceptance-probe.json'
        p.require(not path.exists(), 'public probe already claimed; uncertainty is not retried')
        receipt = {'schemaVersion': 1, 'namespace': t.NAMESPACE, 'status': 'CLAIMED',
                   'kind': 'HERMES763_ACTUAL_TINY_PUBLIC_PROBE', 'claimedAt': time.time(),
                   'sourceBundleSha256': owner['sourceBundleSha256'], 'code': arming['code'],
                   'promptSha256': p.stage.digest(PUBLIC_PROBE_PROMPT.encode()),
                   'tools': [], 'privateContext': False, 'requestsMaximum': 1,
                   'retentionDaysMinimum': 14}
        p.stage.atomic(path, p.stage.encoded(receipt)); before = p.signature(path)
        command = gateway_command(m); p.require(command[-1] == 'gateway-child', 'fixed sealed probe route')
        command[-1] = 'public-probe-child'
        try:
            # Only canonical auth in the namespace; no bot/Calendar secret in
            # this child's env, no service start or Telegram API call.
            result = (run or subprocess.run)(command, env=dict(m['environment']),
                capture_output=True, timeout=40, cwd='/')
            p.stage.atomic(state/'controller/public-probe.stderr', result.stderr)
            p.require(result.returncode == 0 and result.stdout == b'HERMES_NATIVE_OK\n',
                      'one actual supported public probe failed; retained evidence, no retry')
            acceptance_context(m)
            receipt.update(status='DONE', completedAt=time.time(), response='HERMES_NATIVE_OK')
            p.atomic_durable(path, p.stage.encoded(receipt), before)
        except BaseException:
            revoke(m)
            raise
        return {'namespace': t.NAMESPACE, 'tinyPublicProbe': 'DONE', 'native': 'NOT_STARTED',
                'scheduler': 'CLOSED', 'acceptance': 'PENDING'}


def install_acceptance_ingress(m, request):
    """Only the actual authorized /status may enter the armed gateway.

    No upstream admission plugins, commands, session context or model turn run
    during acceptance. The parent claims and acknowledges the one response over
    the existing bot; the RO-controller child cannot manufacture receipts.
    """
    from gateway.run_inbound import GatewayInboundMixin
    from gateway.platforms.event import MessageType
    original = GatewayInboundMixin._handle_message
    async def acceptance_message(runner, event):
        owner = live_owner(m, 'poller')
        if owner['phase'] == 'NATIVE_LIVE':
            return await original(runner, event)
        source = event.source
        if source is None or not runner._is_user_authorized_for_source(source):
            return None
        raw = event.raw_message
        valid = (getattr(source.platform, 'value', None) == 'telegram'
                 and source.chat_type == 'dm' and not source.is_bot
                 and not source.thread_id and not source.profile_route_rejected
                 and not source.delivered_via_upstream_relay
                 and not event.internal and event.allow_gateway_control
                 and event.message_type in {MessageType.TEXT, MessageType.COMMAND}
                 and event.text == '/status' and not event.media_urls
                 and not event.prompt_response and not event.auto_skill
                 and not getattr(raw, 'forward_origin', None)
                 and not getattr(raw, 'forward_date', None)
                 and not getattr(raw, 'sender_chat', None)
                 and event.message_id is not None
                 and isinstance(event.platform_update_id, int)
                 and owner['armedAt'] <= event.timestamp.timestamp() <= time.time() + 2)
        operation = 'acceptance-status' if valid else 'acceptance-unexpected'
        # Identities only, never message bodies/private prompts in the broker.
        request({'operation': operation, 'task': 'status',
                 'args': [str(source.user_id), str(source.chat_id),
                          str(event.message_id), str(event.platform_update_id)]})
        return None  # Already delivered by parent; never adapter send/retry.
    GatewayInboundMixin._handle_message = acceptance_message


def acceptance_context(m):
    owner = live_owner(m, 'poller')
    p.require(owner['phase'] == 'NATIVE_ARMED', 'one initial armed acceptance only')
    arming = t.load(Path(m['paths']['state'])/'controller/arming.json')
    p.require(arming.get('code') == engineering_identity(m)
              and arming.get('sourceBundleSha256') == owner['sourceBundleSha256'],
              'acceptance immutable code/source binding')
    if arming.get('finalGateContinuationSha256'):
        path=Path(m['paths']['state'])/'controller/acceptance-final-gate-continuation.json'; final=t.load(path)
        p.require(p.signature(path)['sha256']==arming['finalGateContinuationSha256']
                  and final.get('kind')=='HERMES763_CANONICAL_DISPLAY_FINAL_GATE_CONTINUATION'
                  and final.get('code')==arming['code'] and final.get('sourceBundleSha256')==owner['sourceBundleSha256']
                  and 0<=time.time()-final.get('recordedAt',0)<=120,
                  'fresh receipt-preserving final controller activation; no vault-write human lease')
    else:
        timed_window(arming['freeze'])
    return owner, arming


def acceptance_status(m, args, *, send=None):
    """Actual sole-gateway ingress plus one durable, non-retried bot response."""
    state = Path(m['paths']['state'])
    with scheduler_transition(m):
        owner, arming = acceptance_context(m)
        secrets = t.load(state/'.secrets.json')
        p.require(isinstance(args, list) and len(args) == 4
                  and all(isinstance(a, str) and re.fullmatch(r'[0-9]{1,20}', a) for a in args),
                  'actual bounded Telegram ingress identities')
        user, chat, message, update = args
        allowed = {s.strip() for s in secrets['TELEGRAM_ALLOWED_USERS'].split(',')}
        p.require(user in allowed and chat == secrets['TELEGRAM_HOME_CHANNEL'] and user == chat,
                  'existing allowed private owner chat only')
        receipt_path = state/'controller/acceptance-inbound.json'
        if receipt_path.exists():
            existing = t.load(receipt_path)
            p.require(existing.get('status') == 'DONE' and existing.get('ingress') == args,
                      'one command already claimed; no send or retry')
            return b'Accepted status already acknowledged.\n'
        receipt = {'schemaVersion': 1, 'namespace': t.NAMESPACE, 'status': 'CLAIMED',
                   'kind': 'HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND', 'ingress': args,
                   'sourceBundleSha256': owner['sourceBundleSha256'], 'code': arming['code'],
                   'claimedAt': time.time(), 'provider': 'NO_MODEL', 'retentionDaysMinimum': 14}
        p.stage.atomic(receipt_path, p.stage.encoded(receipt))
        before = p.signature(receipt_path)
        response = (send or telegram_send_once)(m, chat,
            'Hermes native cutover status: sole native gateway active; scheduler closed; '
            'zero-model /status received and acknowledged. Observation is not accepted yet.', message)
        p.require(response.get('ok') is True and response.get('result', {}).get('message_id') is not None
                  and str(response['result'].get('chat', {}).get('id')) == chat,
                  'actual command acknowledgement required; uncertainty is not retried')
        acceptance_context(m)
        receipt.update(status='DONE', deliveredAt=time.time(),
                       deliveredMessageID=str(response['result']['message_id']))
        p.atomic_durable(receipt_path, p.stage.encoded(receipt), before)
        return b'Actual zero-model command received and acknowledged.\n'


def telegram_send_once(m, chat, text, reply_to=None):
    """One existing-bot HTTPS send; no new bot, poller, fallback or retry."""
    p.require(isinstance(text, str) and 0 < len(text) <= 3500, 'single bounded bot message')
    token = t.load(Path(m['paths']['state'])/'.secrets.json')['TELEGRAM_BOT_TOKEN']
    payload = {'chat_id': chat, 'text': text}
    if reply_to is not None: payload['reply_parameters'] = {'message_id': int(reply_to)}
    request = urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',
        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(65537)
    p.require(len(raw) <= 65536, 'bounded existing-bot acknowledgement')
    return json.loads(raw)


def install_gateway_hooks(m,request):
    """Exact pinned integration, callable offline without starting a gateway."""
    state=Path(m['paths']['state'])
    install_provider_hook(m)
    install_acceptance_ingress(m,request)
    import tools.terminal_tool as terminal
    from tools.registry import registry
    def guarded_terminal(arguments,**kwargs):
        try:
            output=request(terminal_request(arguments))
            return json.dumps({'output':output,'exit_code':0})
        except (ValueError,OSError,EOFError,KeyError,TypeError):
            return json.dumps({'output':'Refused: only reviewed guarded task/read commands; no shell fallback.','exit_code':64})
    registry.register(name='terminal',toolset='terminal',schema=terminal.TERMINAL_SCHEMA,
                      handler=guarded_terminal,check_fn=lambda:True,override=True)
    import cron.scheduler_script as scheduler_script
    def brief_script(script_path,workdir=None,cancel_event=None):
        try:
            p.require(script_path in {'morning-brief.sh',str(state/'scripts/morning-brief.sh')}
                      and workdir==str(state/'workspace/notes'),'exact one managed deterministic brief')
            p.require(not cancel_event or not cancel_event.is_set(),'cancelled brief')
            live_owner(m,'scheduler')
            return True,request({'operation':'brief','task':'morning-brief','args':[]})
        except (ValueError,OSError,EOFError,KeyError,TypeError):
            return False,'Native guarded zero-model brief refused; retained private evidence, no helper delivery or retry.'
    scheduler_script._run_job_script=brief_script
    import cron.scheduler as scheduler
    original_tick=scheduler.tick
    def owned_tick(*args,can_dispatch=None,**kwargs):
        def permitted():
            current=t.load(state/'controller/ownership.json')
            return (current.get('namespace')==t.NAMESPACE and current.get('owner')=='native'
                    and current.get('phase')=='NATIVE_LIVE' and current.get('scheduler')=='ENABLED'
                    and (can_dispatch is None or can_dispatch()))
        try:
            with scheduler_transition(m):
                if not permitted(): return 0
                return original_tick(*args,can_dispatch=permitted,**kwargs)
        except BlockingIOError:
            # A controller transition is in progress. No claim, failure delivery,
            # catch-up or jobs mutation; the next ordinary tick may try again.
            return 0
    scheduler.tick=owned_tick
    # Preserve interrupted-session/kanban history without replaying it. The
    # pinned startup and reconnect paths otherwise synthesize private turns,
    # spawn unguarded workers, or deliver retained notifications automatically.
    # Ordinary fresh ingress and the one guarded NY daily remain independent.
    from gateway.run_startup import GatewayStartupMixin
    GatewayStartupMixin._schedule_resume_pending_sessions=lambda runner,platform=None:0
    GatewayStartupMixin._PRE_RECONNECT_WATCHERS=tuple(
        name for name in GatewayStartupMixin._PRE_RECONNECT_WATCHERS
        if name not in {'_kanban_notifier_watcher','_kanban_dispatcher_watcher'})
    # Disable maintenance/auth/process-control slash routes even for admins.
    # This is an invocation-time guard, not a config list admins can bypass.
    import gateway.slash_access as access
    original_can_run=access.SlashAccessPolicy.can_run
    denied={'restart','update','login','logout','rollback','yolo','terminal','shell','cron',
            'skills','skills-add','skills-remove','reload','reload-mcp','reload-skills',
            'model','codex-runtime','approvals','debug','learn','init','curator','blueprint',
            'suggestions','heartbeat','loop','goal','subgoal','moa','review','refine','browser',
            'usage','kanban','platform','sethome','voice','topup'}
    from hermes_cli.commands import resolve_command
    def can_run(policy,user_id,canonical_cmd):
        definition=resolve_command(canonical_cmd)
        name=definition.name if definition else canonical_cmd
        if name in denied: return False
        return original_can_run(policy,user_id,canonical_cmd)
    access.SlashAccessPolicy.can_run=can_run
    # Pinned dispatch short-circuits can_run when policy.enabled is false. Keep
    # prior ungated access for safe routes, but never bypass our process/auth gate.
    original_policy=access.policy_for_source
    def native_policy(config,source):
        policy=original_policy(config,source)
        if policy.enabled: return policy
        identity=getattr(source,'user_id',None)
        return access.SlashAccessPolicy(enabled=True,
            admin_user_ids=frozenset({str(identity)}) if identity is not None else frozenset(),
            user_allowed_commands=policy.user_allowed_commands)
    access.policy_for_source=native_policy
    # Retain pending ingress instead of first-connect destructive draining. A
    # competing poller must surface a conflict, never delete its queued updates.
    from telegram.ext import Updater
    original_poll=Updater.start_polling
    async def retained_poll(updater,*args,**kwargs):
        live_owner(m,'poller'); kwargs['drop_pending_updates']=False
        return await original_poll(updater,*args,**kwargs)
    Updater.start_polling=retained_poll


def gateway_command(m):
    """Exact namespace also exercised by the installed offline child fixture."""
    state=Path(m['paths']['state']); home=Path(m['paths']['home'])
    metadata=t.PRODUCTION_METADATA.resolve(strict=True)
    p.require(str(metadata).startswith('/nix/store/') and json.loads(metadata.read_bytes())==m,
              'fixed actual immutable production metadata')
    return [m['bubblewrap'],'--unshare-all','--share-net','--die-with-parent','--new-session',
        '--ro-bind','/nix/store','/nix/store','--proc','/proc','--dev','/dev',
        '--tmpfs','/tmp','--tmpfs','/home','--dir','/etc','--ro-bind','/etc/resolv.conf','/etc/resolv.conf',
        '--dir','/usr','--dir','/usr/bin','--dir','/bin',
        '--symlink',m['envBinary'],'/usr/bin/env','--symlink',m['bashBinary'],'/bin/bash',
        '--symlink',m['bashBinary'],'/bin/sh',
        '--bind',str(home),str(home),'--bind',str(state),str(state),
        '--ro-bind',str(state/'controller'),str(state/'controller'),
        '--ro-bind',m['paths']['config'],m['paths']['config'],'--bind',m['paths']['cache'],m['paths']['cache'],
        '--symlink',str(metadata),str(t.PRODUCTION_METADATA),
        '--ro-bind',m['vault'],str(state/'workspace/notes'),'--chdir',str(state),
        m['python'],'-I','-B',str(Path(m['managedAssets'])/'production-runtime.py'),'gateway-child']


def gateway(m):
    """Once native-owned, ANY startup/runtime exit revokes; NAS/CLOSED is untouched."""
    live_owner(m,'poller')
    try:
        return _gateway_owned(m)
    finally:
        revoke(m)


def _gateway_owned(m):
    """One HM foreground supervisor and one contained gateway; no new daemon."""
    state=Path(m['paths']['state']); home=Path(m['paths']['home'])
    owner=live_owner(m,'poller'); live_owner(m,'providerRefresh')
    p.require(m.get('runtimeEngineeringReady') is True,'installed integrated engineering gate')
    receipt=t.load(state/'controller/arming.json')
    p.require(receipt.get('namespace')==t.NAMESPACE and receipt.get('status')=='ARMED'
              and receipt.get('sourceBundleSha256')==t.load(state/'controller/import.json')['sourceBundleSha256'],
              'actual stopped-source/transfer arming receipt')
    observer,scan=local_writer_callbacks(m)
    env=dict(m['environment']); env.update(t.load(state/'.secrets.json'))
    # The only home mounted is the dedicated production HOME. No real notes RW,
    # no workstation CLI grants, SSH agent, user bus, Mac/NAS observer or tunnel.
    command=gateway_command(m)
    parent,child=socket.socketpair()
    env.update(HERMES_PRODUCTION_BROKER_FD=str(child.fileno()),HERMES_NATIVE_READONLY='1')
    process=None
    previous_signals={sig:signal.getsignal(sig) for sig in (signal.SIGTERM,signal.SIGINT)}
    try:
        with writer_module().held_lock(state/'controller/runtime.lock'):
            process=subprocess.Popen(command,env=env,pass_fds=(child.fileno(),),cwd='/')
            child.close()
            def contain(signum,frame):
                revoke(m)
                if process.poll() is None: process.terminate()
                raise SystemExit(64)
            signal.signal(signal.SIGTERM,contain); signal.signal(signal.SIGINT,contain)
            while process.poll() is None:
                try: request=broker_frame(parent)
                except EOFError: break
                operation=''
                try:
                    p.require(isinstance(request,dict) and set(request)=={'operation','task','args'}
                              and isinstance(request['operation'],str),'fixed private broker request')
                    operation=request['operation']
                    if operation=='acceptance-status':
                        p.require(request['task']=='status','fixed initial command')
                        output=acceptance_status(m,request['args'])
                    elif operation=='acceptance-unexpected':
                        p.stage.atomic(state/'controller/unexpected-acceptance-ingress.json',
                                       p.stage.encoded({'observedAt':time.time(),'request':request}))
                        revoke(m); process.terminate()
                        raise ValueError('unexpected authorized acceptance ingress; retained for review')
                    elif operation=='read':
                        current=live_owner(m,'poller')
                        p.require(current['phase']=='NATIVE_LIVE','no private reads before actual acceptance')
                        output=read_task(m,request['task'],request['args'])
                    elif operation in {'write','brief'}:
                        current=live_owner(m,'vaultWrites')
                        p.require(current['phase']=='NATIVE_LIVE','normal writes closed during cutover acceptance')
                        if operation=='brief':
                            live_owner(m,'scheduler'); p.require(request['task']=='morning-brief' and not request['args'],'fixed brief request')
                        else: p.require(request['task'] in WRITE_TASKS,'reviewed gateway task')
                        output=sandboxed_task(m,request['task'],request['args'],observer=observer,scan=scan)
                    else: raise ValueError('no generic broker operation')
                    broker_frame(parent,{'status':'OK','output':output.decode('utf-8')})
                except (ValueError,OSError,KeyError,TypeError,subprocess.SubprocessError):
                    broker_frame(parent,{'status':'REFUSED','output':'Guarded operation refused; private evidence retained.'})
                    # Any incomplete reservation remains sticky. Do not continue
                    # to infer/deliver/retry when committed content needs review.
                    journal=state/'writer-reservation.json'
                    if operation.startswith('acceptance-') or (journal.exists() and t.load(journal).get('status')!='COMPLETE'):
                        revoke(m); process.terminate(); break
            code=process.wait(timeout=30)
            p.require(code==0,'native gateway exited; stopped review required')
    finally:
        parent.close(); child.close()
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        for sig,handler in previous_signals.items(): signal.signal(sig,handler)


SYSTEMD_ENV={'PATH':'/usr/bin:/bin','LANG':'C','XDG_RUNTIME_DIR':'/run/user/1000',
             'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/1000/bus'}


def systemctl(*args):
    return subprocess.run(['/usr/bin/systemctl','--user',*args],env=SYSTEMD_ENV,capture_output=True,check=True,timeout=45).stdout


def timed_window(freeze):
    now=time.time()
    p.require(freeze.get('manualConfirmationSource')=='JOHN_EXECUTION_WINDOW'
              and freeze.get('coordinator')=='omarchy' and set(freeze.get('excludedWriters',[]))==writer_module().WRITERS
              and freeze.get('confirmedAt',0)<=now<freeze.get('expiresAt',0)
              and 0<freeze['expiresAt']-freeze['confirmedAt']<=600,'fresh timed John writer freeze required')


def engineering_identity(m):
    assets=Path(m['managedAssets'])
    # Include task helpers/plugins/closure metadata, not just the seven controller
    # files. A changed tool shim, helper or installed environment invalidates the
    # engineering identity before any source stop/refresh/start can be authorized.
    identity={q.relative_to(assets).as_posix():p.stage.digest(p.stage.read_private(q))
              for q in sorted(assets.rglob('*')) if q.is_file()}
    identity['@metadata']=p.stage.digest(p.stage.encoded(m))
    return identity


def engineering_components(m, request):
    """Run actual immutable offline suites; never accept caller PASS booleans.

    Component success is NOT pre-stop readiness. The separate operator/source/
    acceptance/recovery integration remains required for engineering.json.
    """
    p.require(set(request)=={'taskSources'},'fixed reviewed-code fixture input')
    source=Path(request['taskSources'])
    p.require(source.is_absolute() and source.parent.name.startswith('hermes-763-adapters-')
              and source.parent.parent==Path('/tmp') and source.name=='reviewed-code',
              'private retained reviewed task code only, not a profile or vault import')
    p.stage.safe(source,directory=True,owner=os.getuid())
    hashes=t.load(source/'hashes.json')
    p.require(isinstance(hashes,dict) and 1<=len(hashes)<=64,'bounded reviewed task ledger')
    for name,sha in hashes.items():
        p.relative(name)
        p.require(name.startswith(('.mise/tasks/','scripts/')) and re.fullmatch('[0-9a-f]{64}',sha),
                  'only previously reviewed task code')
        p.require(p.stage.digest(p.stage.read_private(source/name,owner=os.getuid()))==sha
                  and p.stage.digest(p.stage.read_private(Path(m['vault'])/name,owner=os.getuid()))==sha,
                  'reviewed task source drift; no arbitrary fixture code or stale attestation')
    state=Path(m['paths']['state']); profile=Path('/home/johna/.local/state/nix/profiles/home-manager')
    generation=profile.resolve(strict=True)
    p.require(str(generation).startswith('/nix/store/') and generation.name.endswith('-home-manager-generation')
              and t.PRODUCTION_METADATA.resolve(strict=True)==
                  (generation/'home-files/.config/hermes-native/production.json').resolve(strict=True),
              'actual installed generation identity')
    code=engineering_identity(m); owner=p.signature(state/'controller/ownership.json')
    with writer_module().held_lock(state/'controller/runtime.lock'):
        check(m)
        runs=state/'controller/engineering-runs'; p.stage.mkdir(runs)
        retained=Path(tempfile.mkdtemp(prefix='components-',dir=runs)); retained.chmod(0o700)
        suites=[Path(m['productionFixture']),Path(m['writerFixture']),
                Path(m['productionFixture']).with_name('hermes-native-production-state.py')]
        reports=[]
        harness='''import importlib.util,unittest,json,sys,contextlib
s=importlib.util.spec_from_file_location('immutable_fixture',sys.argv[1])
f=importlib.util.module_from_spec(s); s.loader.exec_module(f)
suite=unittest.defaultTestLoader.loadTestsFromModule(f)
def ids(s):
 for item in s:
  if isinstance(item,unittest.TestSuite): yield from ids(item)
  else: yield item.id()
names=sorted(ids(suite))
with contextlib.redirect_stdout(sys.stderr):
 result=unittest.TextTestRunner(stream=sys.stderr).run(suite)
print(json.dumps({'tests':names,'testsRun':result.testsRun,'skipped':len(result.skipped),
                  'failures':len(result.failures),'errors':len(result.errors),'success':result.wasSuccessful()}))
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
'''
        for suite in suites:
            p.require(str(suite).startswith('/nix/store/') and suite.is_file(),'immutable installed fixture only')
            # Relative fixture imports must test the exact installed asset bytes.
            source_assets=suite.parent.parent/'modules/home-manager/hermes-native'
            p.require(all(p.stage.digest(p.stage.read_private(source_assets/n))==sha
                          for n,sha in code.items() if not n.startswith('@')),
                      'fixture source differs from installed runtime')
            result=subprocess.run([m['python'],'-I','-B','-c',harness,str(suite)],cwd='/',
                                  env=dict(m['environment'],HERMES763_TASK_SOURCES=str(source)),
                                  capture_output=True,timeout=180)
            p.stage.atomic(retained/(suite.name+'.stdout'),result.stdout)
            p.stage.atomic(retained/(suite.name+'.stderr'),result.stderr)
            p.require(result.returncode==0,'actual immutable engineering suite failed; retained evidence, not readiness')
            report=json.loads(result.stdout)
            p.require(report['success'] is True and report['testsRun']==len(report['tests'])
                      and report['testsRun']>0 and report['skipped']==report['errors']==report['failures']==0,
                      'all immutable test cases must actually run')
            reports.append({'fixture':str(suite),'sha256':p.stage.digest(p.stage.read_private(suite)),**report})
        required={'test_outer_supervisor_actual_offline_child_exit_and_broker_refusal_revoke',
                  'test_owned_supervisor_setup_failure_revokes_before_any_spawn',
                  'test_complete_installed_gateway_child_namespace_and_hooks_without_network',
                  'test_actual_brief_orchestration_no_model_no_human_lease_stdout_only',
                  'test_actual_brief_profile_symlink_is_not_mounted_and_other_symlinks_still_refuse',
                  'test_noeffect_continuation_requires_fresh_source_window_preserves_checks_and_never_reimports',
                  'test_final_only_continuation_preserves_all_done_receipts_and_rejects_partial_or_drift',
                  'test_preserved_canonical_schedule_display_passes_without_rewriting_or_weakening_daily_guard',
                  'test_only_exact_archived_noeffect_reservation_can_continue_with_fresh_timed_scope',
                  'test_scheduled_brief_normal_policy_requires_no_fresh_human_lease',
                  'test_supported_public_probe_client_one_request_no_tools_history_or_retry',
                  'test_pinned_gateway_registry_scheduler_auth_and_slash_guards_offline',
                  'test_managed_canonical_skills_describe_only_available_guarded_routes',
                  'test_canonical_empty_keyring_coordination_is_retained_not_transported',
                  'test_actual_cold_export_refuses_active_keyring_lock_families_and_inode_drift',
                  'test_pinned_pending_approval_archives_remain_unapproved_outside_active_discovery',
                  'test_actual_pinned_ingress_gate_has_no_model_or_other_command_before_live',
                  'test_canary_exact_create_remove_retained_preimage_and_no_existing_overwrite',
                  'test_brief_claim_precedes_actual_write_and_uncertain_delivery_has_no_retry',
                  'test_actual_canonical_recipe_create_update_and_common_food_upsert_without_generic_write',
                  'test_canonical_invalid_renderer_plan_preserves_real_recipe_and_retained_branch',
                  'test_acceptance_day_is_not_redelivered_before_five_and_dst_next_daily_is_exact',
                  'test_reverse_scheduler_retains_job_identity_source_routes_and_latest_outcome_without_replay'}
        names={name.rsplit('.',1)[-1] for report in reports for name in report['tests']}
        p.require(required<=names,'required integrated lifecycle/brief/normal-policy cases missing')
        check(m)
        p.require(profile.resolve(strict=True)==generation and engineering_identity(m)==code
                  and p.signature(state/'controller/ownership.json')==owner,'engineering/profile/ownership CAS moved')
        for name,sha in hashes.items():
            p.require(p.stage.digest(p.stage.read_private(Path(m['vault'])/name,owner=os.getuid()))==sha,
                      'task code moved during engineering fixtures')
        receipt={'schemaVersion':1,'kind':'HERMES763_ACTUAL_IMMUTABLE_COMPONENT_EVIDENCE',
                 'namespace':t.NAMESPACE,'productionReady':False,'installedGeneration':str(generation),
                 'code':code,'reports':reports,'taskCode':hashes,'recordedAt':time.time(),
                 'runtimeGuard':'PASS','coldImport':'PASS','reverseRecovery':'PASS','writerGate':'PASS',
                 'scope':'OFFLINE_SYNTHETIC_PAYLOADS_NOT_ACTUAL_PRODUCTION_TRANSFER_OR_ACCEPTANCE',
                 'retentionDaysMinimum':14}
        p.stage.atomic(retained/'receipt.json',p.stage.encoded(receipt))
        path=state/'controller/engineering-components.json'
        p.atomic_durable(path,p.stage.encoded(receipt),p.signature(path) if path.exists() else None)
    return {'componentEvidence':'PASS','productionReady':False,'namespace':t.NAMESPACE,
            'testsRun':sum(row['testsRun'] for row in reports),'retained':str(retained)}


REVIEWED_PROVIDERS = {
    '.mise/tasks/get-calendar': 'ae292866161eb2068cf92d315874048c2d430f2a2d3dfab4fe17ce614bcdb6a3',
    '.mise/tasks/get-weather': 'ec5adbe0e8399406f1c1ee4f34e203c35088cf228e3e0f2e3eafe950caba6270',
}


def engineering_providers(m, request):
    """Actual read-only Calendar/weather parity while NAS owns Codex unchanged."""
    check(m)
    p.require(set(request)=={'GOG_KEYRING_PASSWORD'} and isinstance(request['GOG_KEYRING_PASSWORD'],str)
              and 0<len(request['GOG_KEYRING_PASSWORD'])<=4096
              and not any(q in request['GOG_KEYRING_PASSWORD'] for q in '\x00\r\n'),
              'canonical Calendar secret via private stdin only')
    state=Path(m['paths']['state']); generation=Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)
    code=engineering_identity(m); owner=p.signature(state/'controller/ownership.json')
    staging_path=Path('/home/johna/.config/hermes-native/runtime.json')
    p.require(staging_path.resolve(strict=True)==(generation/'home-files/.config/hermes-native/runtime.json').resolve(strict=True),
              'same actual installed staging metadata; no profile source')
    staging=json.loads(staging_path.read_bytes()); source=Path(staging['environment']['GOG_HOME'])
    p.stage.safe(source,directory=True,owner=os.getuid())
    snapshot={q.relative_to(source).as_posix():p.signature(q) for q in sorted(source.rglob('*')) if q.is_file()}
    p.require(snapshot and all(not q.is_symlink() for q in source.rglob('*')), 'canonical Google context without symlinks')
    runs=state/'controller/engineering-runs'; p.stage.mkdir(runs)
    root=Path(tempfile.mkdtemp(prefix='providers-',dir=runs)); root.chmod(0o700)
    shutil.copytree(source,root/'gogcli')
    for q in (root/'gogcli').rglob('*'):
        q.chmod(0o700 if q.is_dir() else 0o600)
    for name in ['home','hermes','config','cache','data','state']: p.stage.mkdir(root/name)
    env={k:v for k,v in m['environment'].items() if not k.endswith(('TOKEN','API_KEY'))
         and not k.startswith(('PI_','CLAUDE_','HERMES_PRODUCTION_'))}
    env.update(HOME=str(root/'home'),HERMES_HOME=str(root/'hermes'),GOG_HOME=str(root/'gogcli'),
               GOG_KEYRING_PASSWORD=request['GOG_KEYRING_PASSWORD'],GOG_KEYRING_BACKEND='file',GOG_READONLY='1',
               TZ='America/New_York',HERMES_NATIVE_READONLY='1')
    for key,name in [('XDG_CONFIG_HOME','config'),('XDG_CACHE_HOME','cache'),('XDG_DATA_HOME','data'),('XDG_STATE_HOME','state')]:
        env[key]=str(root/name)
    reports={}
    for task in ['get-calendar','get-weather']:
        name='.mise/tasks/'+task; script=Path(m['vault'])/name
        p.require(p.stage.digest(p.stage.read_private(script,owner=os.getuid()))==REVIEWED_PROVIDERS[name],
                  'previously reviewed actual provider task code drift')
        command=[m['bubblewrap'],'--unshare-all','--share-net','--die-with-parent','--new-session',
                 '--ro-bind','/nix/store','/nix/store','--proc','/proc','--dev','/dev',
                 '--tmpfs','/tmp','--tmpfs','/home','--dir','/etc','--ro-bind','/etc/resolv.conf','/etc/resolv.conf',
                 '--bind',str(root),str(root),'--ro-bind',str(script),'/tmp/provider.py','--chdir','/',
                 m['python'],'-I','-B','/tmp/provider.py','--format=json']
        with (root/(task+'.stdout')).open('xb') as output,(root/(task+'.stderr')).open('xb') as errors:
            os.fchmod(output.fileno(),0o600); os.fchmod(errors.fileno(),0o600)
            result=subprocess.run(command,env=env,cwd='/',stdout=output,stderr=errors,timeout=270 if task=='get-calendar' else 20)
        raw=p.stage.read_private(root/(task+'.stdout')); p.require(result.returncode==0 and len(raw)<=4*1024*1024,
            'actual read-only provider failed; private evidence retained, no fallback/login')
        data=json.loads(raw)
        if task=='get-calendar':
            p.require(data.get('failed_accounts')==[] and isinstance(data.get('items'),list),
                      'both actual canonical Calendars must pass; partial output is not readiness')
        else:
            p.require(isinstance(data.get('current_condition'),list) and data['current_condition']
                      and isinstance(data.get('weather'),list) and data['weather'], 'actual public weather response required')
        reports[task]={'status':'PASS','taskSha256':REVIEWED_PROVIDERS[name],
                       'outputSha256':p.stage.digest(raw),'observedAt':time.time()}
    check(m)
    p.require(Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)==generation
              and engineering_identity(m)==code and p.signature(state/'controller/ownership.json')==owner
              and snapshot=={q.relative_to(source).as_posix():p.signature(q) for q in sorted(source.rglob('*')) if q.is_file()},
              'provider source/profile/CLOSED ownership CAS changed')
    for name,sha in REVIEWED_PROVIDERS.items():
        p.require(p.stage.digest(p.stage.read_private(Path(m['vault'])/name,owner=os.getuid()))==sha,'provider code changed')
    receipt={'schemaVersion':1,'namespace':t.NAMESPACE,'kind':'HERMES763_ACTUAL_READONLY_PROVIDER_EVIDENCE',
             'status':'PASS','installedGeneration':str(generation),'code':code,'reports':reports,
             'canonicalGoogleSource':str(source),'sourceFiles':snapshot,'retained':str(root),
             'mutations':'NONE','codex':'NOT_READ_NOT_RESOLVED','recordedAt':time.time(),'retentionDaysMinimum':14}
    p.stage.atomic(root/'receipt.json',p.stage.encoded(receipt))
    path=state/'controller/engineering-providers.json'
    p.atomic_durable(path,p.stage.encoded(receipt),p.signature(path) if path.exists() else None)
    return {'namespace':t.NAMESPACE,'readOnlyProviders':'PASS','calendarAccounts':2,'weather':'PASS',
            'productionReady':False,'retained':str(root)}


def engineering_ready(m, request):
    """Join actual installed, provider, retained NAS and live metadata evidence."""
    p.require(isinstance(request,dict) and set(request)=={'operatorEvidence','sourceBaseline','peers','packet'},
              'fixed actual integration evidence, never caller PASS flags')
    check(m)
    state=Path(m['paths']['state']); control=state/'controller'
    generation=Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)
    code=engineering_identity(m); owner=p.signature(control/'ownership.json')
    component=t.load(control/'engineering-components.json')
    providers=t.load(control/'engineering-providers.json')
    for row,kind in [(component,'HERMES763_ACTUAL_IMMUTABLE_COMPONENT_EVIDENCE'),
                     (providers,'HERMES763_ACTUAL_READONLY_PROVIDER_EVIDENCE')]:
        p.require(row.get('kind')==kind and row.get('namespace')==t.NAMESPACE
                  and row.get('installedGeneration')==str(generation) and row.get('code')==code,
                  'actual own retained receipt for this installed code/generation')
    p.require(component.get('productionReady') is False and component.get('reports')
              and all(q.get('success') is True and q.get('testsRun')==len(q.get('tests',[])) and q['testsRun']>0
                      and q.get('skipped')==q.get('failures')==q.get('errors')==0 for q in component['reports']),
              'all actual immutable component cases executed')
    for row in component['reports']:
        fixture=Path(row['fixture']); p.require(str(fixture).startswith('/nix/store/')
            and p.stage.digest(p.stage.read_private(fixture))==row['sha256'],'immutable executed fixture hash')
    p.require(set(providers.get('reports',{}))=={'get-calendar','get-weather'}
              and all(q.get('status')=='PASS' and 0<=time.time()-q.get('observedAt',0)<=600
                      for q in providers['reports'].values()),'fresh actual read-only Calendar/weather evidence')
    for name,row in providers['reports'].items():
        p.require(row['taskSha256']==REVIEWED_PROVIDERS['.mise/tasks/'+name]
                  and p.stage.digest(p.stage.read_private(Path(providers['retained'])/(name+'.stdout')))==row['outputSha256'],
                  'actual private provider output receipt binding')
    packet=request['packet']; operator=request['operatorEvidence']; baseline=request['sourceBaseline']
    packet_sha=p.stage.digest(p.stage.encoded(packet))
    hashes={name:p.stage.digest(base64.b64decode(raw,validate=True)) for name,raw in packet['files'].items()}
    p.require(packet.get('namespace')==t.NAMESPACE and packet.get('installedGeneration')==str(generation)
              and operator.get('kind')=='HERMES763_ACTUAL_RETAINED_OPERATOR_ENGINEERING'
              and operator.get('namespace')==t.NAMESPACE and operator.get('installedGeneration')==str(generation)
              and operator.get('packetSha256')==packet_sha and operator.get('files')==hashes
              and operator.get('sourceBaseline')==baseline
              and operator.get('sourceCredentials')=='NOT_READ' and 0<=time.time()-operator.get('recordedAt',0)<=300,
              'actual retained matching NAS/operator code and unchanged source')
    live=baseline.get('running') is True and baseline.get('pid',0)>0 and baseline.get('restartPolicy')=='unless-stopped' and baseline.get('retirementPresent') is False
    if live:
        p.require(operator.get('sourceRuntime')=='UNCHANGED_LIVE','actual sole live NAS source required')
    else:
        proof=operator.get('sourceStoppedProof',{})
        p.require(operator.get('sourceRuntime')=='UNCHANGED_STOPPED' and baseline.get('running') is False
                  and baseline.get('pid')==0 and baseline.get('restartPolicy')=='no' and baseline.get('retirementPresent') is True
                  and proof.get('running') is False and proof.get('pid')==0 and proof.get('restartPolicy')=='no'
                  and proof.get('managedRetirement') is True and proof.get('revision')==p.stage.REVISION
                  and proof.get('containerID')==baseline.get('containerID') and proof.get('imageID')==baseline.get('imageID')
                  and re.fullmatch('[0-9a-f]{64}',proof.get('retirementSha256','')) is not None
                  and 0<=time.time()-proof.get('observedAt',0)<=300,
                  'exact retained SOURCE_STOPPED continuation; native must remain CLOSED')
    for name in ['production-transfer.py','production-state.py','state-stage.py']:
        p.require(hashes.get(name)==code[name],'source and installed native transfer implementation must match')
    reports=operator.get('reports',[])
    p.require({q.get('fixture') for q in reports}=={'tests/test_hermes_ops.py','tests/test_hermes_cutover_source.py'}
              and all(q.get('sha256')==hashes[q['fixture']] and q.get('success') is True
                      and q.get('testsRun')==len(q.get('tests',[])) and q['testsRun']>0
                      and q.get('skipped')==q.get('failures')==q.get('errors')==0 for q in reports),
              'actual retained lifecycle/deploy-guard suites, not flags')
    names={name.rsplit('.',1)[-1] for row in reports for name in row['tests']}
    p.require({'test_bounded_cutover_vertical_order_keeps_acceptance_closed_and_no_auto_resume',
               'test_stopped_continuation_requires_fresh_freeze_and_exact_retirement_without_source_restart',
               'test_source_code_stopped_continuation_preserves_exact_protection',
               'test_acceptance_requires_actual_inbound_before_any_canary_brief_or_live',
               'test_acceptance_vertical_order_and_uncertain_delivery_containment_no_retry_resume',
               'test_recovery_uses_separate_fresh_proofs_and_never_rewrites_approved_payload',
               'test_retired_source_no_mkdir_rsync_build_pull_or_up'}<=names,'required integrated operator cases')
    writer_module().peer_check(request['peers'],[],time.time())
    tasks=component['taskCode']
    p.require(set(REVIEWED_PROVIDERS)<=set(tasks),'reviewed provider code in exact task ledger')
    for name,sha in tasks.items():
        p.relative(name);p.require(name.startswith(('.mise/tasks/','scripts/'))
            and p.stage.digest(p.stage.read_private(Path(m['vault'])/name,owner=os.getuid()))==sha,'reviewed live task code CAS')
    source=Path('/home/johna/dev/src/system-config-amfaro')
    source_hashes={name:p.stage.digest(p.stage.read_private(source/'modules/home-manager/hermes-native'/name,owner=os.getuid()))
                   for name in code if not name.startswith('@')}
    p.require(all(source_hashes[name]==code[name] for name in source_hashes),'actual active source matches immutable assets')
    source_hashes['@flake.lock']=p.stage.digest(p.stage.read_private(source/'flake.lock',owner=os.getuid()))
    ledger={'kind':'REVIEWED_USER_OWNED_VAULT_TASK_CODE','namespace':t.NAMESPACE,'files':tasks,
            'installedGeneration':str(generation),'componentEvidenceSha256':p.signature(control/'engineering-components.json')['sha256']}
    prior=t.load(control/'engineering.json') if (control/'engineering.json').exists() else {}
    initial_generation=prior.get('initialGeneration',prior.get('installedGeneration',str(generation)))
    receipt={'initialGeneration':initial_generation,'schemaVersion':1,'kind':'HERMES763_ACTUAL_PRESTOP_ENGINEERING','namespace':t.NAMESPACE,
             'revision':p.stage.REVISION,'productionReady':True,'installedGeneration':str(generation),'code':code,
             'componentEvidenceSha256':ledger['componentEvidenceSha256'],
             'providerEvidenceSha256':p.signature(control/'engineering-providers.json')['sha256'],
             'operatorEvidence':operator,'nasPacketSha256':packet_sha,'sourceBaseline':baseline,
             'sourceCheckpoint':'LIVE_PRESTOP' if live else 'STOPPED_CONTINUATION',
             'sourceHashes':source_hashes,'taskCode':tasks,'peers':request['peers'],'recordedAt':time.time(),
             'runtimeGuard':'PASS','coldImport':'PASS','reverseRecovery':'PASS','writerGate':'PASS',
             'nasRedeployGuard':'PASS','sourceProfileCAS':'PASS','syncthingConvergence':'PASS',
             'scope':'READY_FOR_FRESH_HUMAN_WINDOW_NOT_PRODUCTION_TRANSFER_OR_ACCEPTANCE','retentionDaysMinimum':14}
    check(m)
    p.require(generation==Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)
              and engineering_identity(m)==code and p.signature(control/'ownership.json')==owner,'ready evidence CAS moved')
    for name,sha in source_hashes.items():
        path=source/'flake.lock' if name=='@flake.lock' else source/'modules/home-manager/hermes-native'/name
        p.require(p.stage.digest(p.stage.read_private(path,owner=os.getuid()))==sha,'active source changed during ready join')
    for path,value in [(control/'task-code.json',ledger),(control/'engineering.json',receipt)]:
        p.atomic_durable(path,p.stage.encoded(value),p.signature(path) if path.exists() else None)
    return receipt


def engineering_evidence(m):
    """Read actual complete pre-stop evidence; component PASS never promotes itself."""
    check(m)
    state=Path(m['paths']['state']); receipt=t.load(state/'controller/engineering.json')
    generation=Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)
    p.require(receipt.get('kind')=='HERMES763_ACTUAL_PRESTOP_ENGINEERING'
              and receipt.get('namespace')==t.NAMESPACE and receipt.get('revision')==p.stage.REVISION
              and receipt.get('productionReady') is True and receipt.get('installedGeneration')==str(generation)
              and receipt.get('code')==engineering_identity(m)
              and all(receipt.get(k)=='PASS' for k in ['runtimeGuard','coldImport','reverseRecovery','writerGate',
                                                       'nasRedeployGuard','sourceProfileCAS','syncthingConvergence']),
              'complete current installed pre-stop evidence required; component flags are not readiness')
    p.require(0<=time.time()-receipt.get('recordedAt',0)<=600,'fresh integrated ready-window receipt')
    providers=state/'controller/engineering-providers.json'
    p.require(p.signature(providers)['sha256']==receipt.get('providerEvidenceSha256')
              and all(0<=time.time()-row.get('observedAt',0)<=600 for row in t.load(providers)['reports'].values()),
              'actual provider receipt remains current before source stop')
    source=Path('/home/johna/dev/src/system-config-amfaro')
    for name,sha in receipt['sourceHashes'].items():
        path=source/'flake.lock' if name=='@flake.lock' else source/'modules/home-manager/hermes-native'/name
        p.require(p.stage.digest(p.stage.read_private(path,owner=os.getuid()))==sha,'source/independent lock CAS moved; review before source stop')
    component=state/'controller/engineering-components.json'
    p.require(p.signature(component)['sha256']==receipt.get('componentEvidenceSha256'),
              'actual immutable component receipt binding required')
    ledger=t.load(state/'controller/task-code.json')
    p.require(ledger.get('kind')=='REVIEWED_USER_OWNED_VAULT_TASK_CODE' and ledger.get('namespace')==t.NAMESPACE
              and ledger.get('files')==receipt.get('taskCode'),'actual reviewed task ledger identity')
    for name,sha in ledger['files'].items():
        p.relative(name)
        p.require(name.startswith(('.mise/tasks/','scripts/'))
                  and p.stage.digest(p.stage.read_private(Path(m['vault'])/name,owner=os.getuid()))==sha,
                  'actual task code drift before source stop')
    return receipt


def arm(m, request, *, ingress=None):
    """No source stop, login, refresh or model call here; exact stopped transfer only."""
    state=Path(m['paths']['state']); control=state/'controller'; owner_path=control/'ownership.json'
    p.require(m.get('runtimeEngineeringReady') is True,'installed integrated engineering runtime')
    engineering=t.load(control/'engineering.json')
    p.require(engineering.get('kind')=='HERMES763_ACTUAL_PRESTOP_ENGINEERING'
              and engineering.get('namespace')==t.NAMESPACE and engineering.get('productionReady') is True
              and engineering.get('code')==engineering_identity(m)
              and all(engineering.get(k)=='PASS' for k in ['runtimeGuard','coldImport','reverseRecovery','writerGate',
                                                         'nasRedeployGuard','sourceProfileCAS','syncthingConvergence'])
              and p.signature(control/'engineering-components.json')['sha256']==engineering.get('componentEvidenceSha256'),
              'actual installed integration evidence; component flags alone cannot arm')
    p.require(request.get('kind')=='HERMES763_ARM_STOPPED_SOURCE' and request.get('namespace')==t.NAMESPACE,'arming identity')
    timed_window(request['freeze'])
    proof=request['sourceProof']
    p.require(proof.get('running') is False and proof.get('pid')==0 and proof.get('restartPolicy')=='no'
              and proof.get('managedRetirement') is True and proof.get('revision')==p.stage.REVISION
              and 0<=time.time()-proof.get('observedAt',0)<=30
              and re.fullmatch(r'sha256:[0-9a-f]{64}',proof.get('imageID',''))
              and re.fullmatch(r'[0-9a-f]{64}',proof.get('containerID',''))
              and re.fullmatch(r'[0-9a-f]{64}',proof.get('retirementSha256','')),'fresh stopped-source exclusive ownership')
    imported=t.load(control/'import.json'); bundle=t.load(Path(imported['sourceBundle']))
    p.require(request.get('sourceBundleSha256')==imported['sourceBundleSha256']
              and proof.get('imageID')==bundle['sourceProof'].get('imageID')
              and proof.get('containerID')==bundle['sourceProof'].get('containerID')
              and proof.get('retirementSha256')==bundle['sourceProof'].get('retirementSha256'), 'stopped source transfer identity')
    owner=t.load(owner_path); expected=p.signature(owner_path)
    p.require(owner.get('owner')=='nas' and owner.get('phase')=='CLOSED','no implicit rearming/recovery')
    for label,root in [('state',state),('home',Path(m['paths']['home']))]:
        p.require(all(p.signature(root/n)==signature for n,signature in imported['files'][label].items()),'closed imported payload drift')
    writer_module().peer_check(request['peers'],{},time.time())
    actual=systemctl('show',m['service'],'-p','ActiveState','-p','MainPID','-p','Restart','-p','RefuseManualStart')
    row=dict(q.split('=',1) for q in actual.decode().splitlines() if '=' in q)
    p.require(row.get('ActiveState')=='inactive' and row.get('MainPID')=='0' and row.get('Restart')=='no'
              and row.get('RefuseManualStart')=='yes','actual untouched inactive manual-start unit')
    p.require(not (control/'arming.json').exists(),'existing incomplete arming requires review')
    p.require(not (control/'pending-ingress.json').exists(),'previous ingress classification requires review; no implicit retry')
    # Classify pending ingress WITHOUT acknowledging/dropping queued updates.
    # This request exists only after the actual sole stopped owner and freeze.
    if ingress is None:
        token=t.load(state/'.secrets.json')['TELEGRAM_BOT_TOKEN']
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/getUpdates',
            data=json.dumps({'timeout':0,'limit':100}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=15) as response: pending=json.load(response)
    else: pending=ingress()
    p.stage.atomic(control/'pending-ingress.json',p.stage.encoded(pending))
    p.require(pending.get('ok') is True and pending.get('result')==[],
              'unclassified pending Telegram ingress retained; no drop/replay/start')
    timed_window(request['freeze'])
    receipt={'schemaVersion':1,'namespace':t.NAMESPACE,'status':'ARMED',
        'sourceBundleSha256':imported['sourceBundleSha256'],'sourceProof':proof,'freeze':request['freeze'],
        'code':engineering_identity(m),'armedAt':time.time(),'retentionDaysMinimum':14,
        'ingress':'ACTUAL_EMPTY_NO_ACK_NO_DROP','providerResolver':'SUPPORTED_CANONICAL_NATIVE_ONLY',
        'poller':'SOLE_NATIVE','scheduler':'DISABLED_UNTIL_INITIAL_ACCEPTANCE','nasResume':'NO_AUTOMATIC_ROUTE'}
    p.stage.atomic(control/'arming.json',p.stage.encoded(receipt))
    owner.update(owner='native',phase='NATIVE_ARMED',poller='ENABLED',providerRefresh='ENABLED',
                 scheduler='DISABLED',vaultWrites='ENABLED',normalWriterPolicy='NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION',
                 armedAt=receipt['armedAt'],sourceBundleSha256=receipt['sourceBundleSha256'])
    p.atomic_durable(owner_path,p.stage.encoded(owner),expected)
    return {'namespace':t.NAMESPACE,'ownership':'NATIVE_ARMED','scheduler':'CLOSED','normalWrites':'CLOSED',
            'ingress':'EMPTY_RETAINED','native':'NOT_STARTED','nas':'STOPPED_NOT_RESUMED'}


def start(m):
    """Explicit controller-only activation; no boot/login restart or linger change."""
    owner=live_owner(m,'poller'); state=Path(m['paths']['state'])
    receipt=t.load(state/'controller/arming.json')
    p.require(owner['phase']=='NATIVE_ARMED' and receipt['status']=='ARMED' and receipt['code']==engineering_identity(m),
              'exact fresh installed native arming')
    acceptance_context(m)
    recorded_acceptance(m,'acceptance-probe.json','HERMES763_ACTUAL_TINY_PUBLIC_PROBE')
    dropin=Path('/run/user/1000/systemd/user/hermes-production.service.d/763-cutover.conf')
    if dropin.exists():
        final=state/'controller/acceptance-final-gate-continuation.json'
        continuation=t.load(final if final.exists() else state/'controller/acceptance-noeffect-continuation.json')
        p.require(continuation.get('kind') in {'HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION',
                                             'HERMES763_CANONICAL_DISPLAY_FINAL_GATE_CONTINUATION'}
                  and continuation.get('code')==receipt['code']
                  and continuation.get('sourceBundleSha256')==receipt['sourceBundleSha256']
                  and p.stage.read_private(dropin,owner=os.getuid())==b'[Unit]\nRefuseManualStart=false\n',
                  'only exact retained cutover override after reviewed continuation')
    else:
        p.require(not dropin.is_symlink(),'unowned runtime unit override preserved')
        p.stage.atomic(dropin,b'[Unit]\nRefuseManualStart=false\n')
    try:
        systemctl('daemon-reload'); systemctl('start',m['service'])
        actual=systemctl('show',m['service'],'-p','ActiveState','-p','MainPID','-p','Restart')
        row=dict(q.split('=',1) for q in actual.decode().splitlines() if '=' in q)
        p.require(row.get('ActiveState')=='active' and int(row.get('MainPID','0'))>0 and row.get('Restart')=='no',
                  'actual foreground native service start')
        return {'native':'STARTED_NOT_ACCEPTED','namespace':t.NAMESPACE,'mainPID':int(row['MainPID']),
                'scheduler':'CLOSED','observation':'PENDING'}
    except BaseException:
        revoke(m)
        systemctl('stop',m['service'])
        raise


def maintenance_callbacks(m, scope, observe):
    """Wait only for convergence caused by THIS writer's own selected scan."""
    _, local_scan = local_writer_callbacks(m)
    waiting = False
    def scan(names):
        nonlocal waiting
        local_scan(names); waiting = True
    def actual_peers(names):
        nonlocal waiting
        deadline = min(time.monotonic() + 60,
                       time.monotonic() + max(0, scope['expiresAt'] - time.time()))
        while True:
            live_owner(m, 'vaultWrites')
            writer_module().scope_check(scope, names, time.time())
            rows = observe(names)  # New actual observations, never retimestamped.
            try:
                writer_module().peer_check(rows, {}, time.time())
                waiting = False
                return rows
            except ValueError:
                p.require(waiting and time.monotonic() < deadline, 'maintenance peer convergence required')
                p.require(set(rows) == set(writer_module().PEERS), 'existing all-peer topology required')
                for i, name in enumerate(writer_module().PEERS):
                    row = rows[name]
                    adjacent = sorted(q for j, q in enumerate(writer_module().PEERS) if abs(i-j) == 1)
                    p.require(row.get('folderID') == 'notes' and row.get('type') == 'sendreceive'
                              and row.get('paused') is False and row.get('connectedPeers') == adjacent
                              and row.get('conflicts') == [] and row.get('errors') == 0 and row.get('pullErrors') == 0
                              and 0 <= time.time() - row.get('observedAt', 0) <= 5
                              and row.get('state') in {'idle', 'scanning', 'scan-waiting', 'sync-waiting', 'syncing'}
                              and isinstance(row.get('completion'), (int, float)) and 0 <= row['completion'] <= 100
                              and all(isinstance(row.get(k), int) and row[k] >= 0 for k in ['needItems', 'needBytes']),
                              'maintenance conflict/error/topology/config failure; no waiting waiver')
                time.sleep(.2)
    return actual_peers, scan


def maintenance_task(m, request, observe):
    """Fresh operator observations over this invocation's SSH stdin, not a service."""
    live_owner(m,'vaultWrites')
    task,args=request['task'],request['args']; files=task_targets(task,args)
    scope=request['scope']; writer_module().scope_check(scope,files,time.time())
    actual_peers,scan=maintenance_callbacks(m,scope,observe)
    output=sandboxed_task(m,task,args,scope=scope,observer=actual_peers,scan=scan)
    return {'task':'COMPLETE','namespace':t.NAMESPACE,'outputBase64':base64.b64encode(output).decode(),
            'provider':'NO_MODEL','delivery':'STDOUT_ONLY','retentionDaysMinimum':14}


CANARY_NAME = 'journal/hermes-native-763-canary.md'
CANARY_BYTES = b'# Hermes native cutover canary\n\nPublic disposable synchronization acceptance marker.\n'


def acceptance_canary(m, request, observe):
    """Exact public disposable file only; distinct creation/removal reservations."""
    state, vault = Path(m['paths']['state']), Path(m['vault'])
    with scheduler_transition(m):
        owner, arming = acceptance_context(m)
        p.require(set(request) == {'createScope', 'removeScope'}, 'fixed canary scopes')
        w = writer_module(); files = (CANARY_NAME,)
        for scope in request.values(): w.scope_check(scope, files, time.time())
        p.require(request['createScope']['nonce'] != request['removeScope']['nonce'], 'distinct canary removal authority')
        receipt_path = state/'controller/acceptance-canary.json'
        p.require(not receipt_path.exists(), 'canary already claimed; no automatic cleanup/retry')
        receipt = {'schemaVersion': 1, 'namespace': t.NAMESPACE, 'status': 'CLAIMED',
                   'kind': 'HERMES763_ACTUAL_SYNCED_CANARY', 'file': CANARY_NAME,
                   'contentSha256': p.stage.digest(CANARY_BYTES), 'claimedAt': time.time(),
                   'sourceBundleSha256': owner['sourceBundleSha256'], 'code': arming['code'],
                   'retentionDaysMinimum': 14}
        p.stage.atomic(receipt_path, p.stage.encoded(receipt)); before = p.signature(receipt_path)
        observer, scan = maintenance_callbacks(m, request['createScope'], observe)
        with w.reserve(state, vault, files, scope=request['createScope'], observer=observer) as reservation:
            p.require(reservation.expected[CANARY_NAME] is None, 'existing canary path preserved; no overwrite')
            reservation.check(); acceptance_context(m)
            p.atomic_durable(vault/CANARY_NAME, CANARY_BYTES, None)
            final = w.manifest(vault, files)
            p.require(final[CANARY_NAME]['sha256'] == receipt['contentSha256'], 'canary exact local readback')
            scan(files); reservation.complete(final)
        receipt.update(status='CREATED_CONVERGED', createdPostimage=final[CANARY_NAME])
        p.atomic_durable(receipt_path, p.stage.encoded(receipt), before); before = p.signature(receipt_path)
        observer, scan = maintenance_callbacks(m, request['removeScope'], observe)
        with w.reserve(state, vault, files, scope=request['removeScope'], observer=observer) as reservation:
            p.require(reservation.expected[CANARY_NAME] == final[CANARY_NAME], 'only owned exact canary may be removed')
            reservation.check(); acceptance_context(m)
            # Private retained preimage already created by reserve(). No generic
            # delete/restore route, and no other vault path is reachable here.
            p.require(p.signature(vault/CANARY_NAME) == final[CANARY_NAME], 'canary removal CAS')
            os.unlink(vault/CANARY_NAME)
            fd = os.open(vault/'journal', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try: os.fsync(fd)
            finally: os.close(fd)
            removed = w.manifest(vault, files); p.require(removed == {CANARY_NAME: None}, 'canary absent readback')
            scan(files); reservation.complete(removed)
        acceptance_context(m)
        receipt.update(status='DONE', removedAt=time.time(), creationNonce=request['createScope']['nonce'],
                       removalNonce=request['removeScope']['nonce'], convergence='ACTUAL_ALL_PEER_METADATA')
        p.atomic_durable(receipt_path, p.stage.encoded(receipt), before)
        return {'namespace': t.NAMESPACE, 'syncedCanary': 'DONE', 'retentionDaysMinimum': 14}


def recorded_acceptance(m, name, kind):
    owner, arming = acceptance_context(m)
    return retained_acceptance(m,name,kind,owner,arming)


def retained_acceptance(m, name, kind, owner, arming):
    """Validate bytes against their actual arming lineage, also while contained."""
    path = Path(m['paths']['state'])/'controller'/name
    receipt = t.load(path)
    sha=p.signature(path)['sha256']
    current=receipt.get('code') == arming['code']
    if not current and name in {'acceptance-probe.json','acceptance-inbound.json','acceptance-canary.json'}:
        review=t.load(Path(m['paths']['state'])/'controller/acceptance-noeffect-continuation.json')
        current=(review.get('kind')=='HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION'
                 and review.get('code')==arming['code']
                 and review.get('sourceBundleSha256')==owner['sourceBundleSha256']
                 and review.get('previousCode')==receipt.get('code')
                 and review.get('preservedReceipts',{}).get(name)==sha
                 and p.stage.read_private(Path(review['archive'])/name,owner=os.getuid())
                     == p.stage.read_private(path,owner=os.getuid()))
    final=Path(m['paths']['state'])/'controller/acceptance-final-gate-continuation.json'
    if not current and final.exists() and name in dict(ACCEPTANCE_KINDS):
        review=t.load(final)
        current=(review.get('kind')=='HERMES763_CANONICAL_DISPLAY_FINAL_GATE_CONTINUATION'
                 and review.get('namespace')==t.NAMESPACE and review.get('code')==arming['code']
                 and review.get('sourceBundleSha256')==owner['sourceBundleSha256']
                 and review.get('preservedReceipts',{}).get(name)==sha
                 and review.get('receiptCodes',{}).get(name)==receipt.get('code')
                 and p.stage.read_private(Path(review['archive'])/name,owner=os.getuid())
                     ==p.stage.read_private(path,owner=os.getuid()))
    p.require(receipt.get('namespace') == t.NAMESPACE and receipt.get('status') == 'DONE'
              and receipt.get('kind') == kind and current
              and receipt.get('sourceBundleSha256') == owner['sourceBundleSha256'],
              'actual retained acceptance receipt required; caller PASS is not evidence')
    return receipt, sha


def brief_noeffect(m):
    """Read-only proof of this exact profile-symlink pre-process incident, not retry authority."""
    check(m); t.native_stopped(m)
    state=Path(m['paths']['state']); control=state/'controller'
    owner=t.load(control/'ownership.json'); arming=t.load(control/'arming.json')
    claim=t.load(control/'acceptance-brief.json'); reservation=t.load(state/'writer-reservation.json')
    p.require(owner.get('phase')=='STOPPED_REVIEW_REQUIRED' and arming.get('status')=='ARMED'
              and claim.get('status')=='CLAIMED' and claim.get('kind')=='HERMES763_ACTUAL_ZERO_MODEL_BRIEF'
              and claim.get('code')==arming.get('code')
              and claim.get('sourceBundleSha256')==owner.get('sourceBundleSha256')==arming.get('sourceBundleSha256')
              and not (control/'acceptance-brief.stdout').exists()
              and not (control/'initial-acceptance.json').exists(), 'exact claimed pre-live brief incident only')
    files=tuple(claim.get('files',[]))
    p.require(files==task_targets('morning-brief',[]) and reservation.get('status')=='STOPPED_REVIEW_REQUIRED'
              and tuple(reservation.get('expected',{}))==files, 'exact stopped brief reservation')
    nonce=state/'reservation-evidence'/(p.stage.digest(reservation['nonce'].encode())+'.json')
    p.require(p.stage.read_private(nonce,owner=os.getuid())==p.stage.encoded(reservation),
              'original reservation evidence binding')
    p.require(writer_module().manifest(Path(m['vault']),files)==reservation['expected'],
              'original brief journal signature unchanged; no vault restore')
    for name,signature in reservation['expected'].items():
        p.require(signature is not None
                  and p.stage.digest(p.stage.read_private(Path(reservation['preimages'])/name,owner=os.getuid()))==signature['sha256'],
                  'exact retained brief preimage')
    runs=list((control/'task-runs').iterdir())
    p.require(len(runs)==1 and runs[0].is_dir() and not any(runs[0].iterdir())
              and claim['claimedAt']<=runs[0].stat().st_mtime<=claim['claimedAt']+5,
              'exact empty pre-process run; unknown/partial task effects are never retried')
    profile=Path(m['vault'])/'CLAUDE.md'
    p.require(profile.is_symlink() and profile.lstat().st_uid==os.getuid()
              and os.readlink(profile)=='AGENTS.md', 'exact unchanged unrelated agent-profile symlink')
    original=t.load(control/'engineering.json')
    # The old immutable closure, not a caller explanation, proves failure order.
    # After a new engineering run, the original generation is retained in arming.
    generation=arming.get('initialGeneration',original.get('initialGeneration',original['installedGeneration']))
    old_metadata=(Path(generation)/'home-files/.config/hermes-native/production.json').resolve(strict=True)
    p.require(str(old_metadata).startswith('/nix/store/'),'retained immutable initial metadata')
    old=json.loads(old_metadata.read_bytes())
    old_assets=Path(old['managedAssets']); previous=arming['code']
    p.require(str(old_assets).startswith('/nix/store/')
              and engineering_identity(old)==previous, 'original actual immutable incident code')
    source=p.stage.read_private(old_assets/'production-runtime.py').decode()
    p.require("for entry in sorted(vault.iterdir()):\n            p.stage.safe(entry" in source
              and source.index('for entry in sorted(vault.iterdir()):')<source.index("index=run/'obsidian'")
                  <source.index('result=subprocess.run([*argv'), 'pinned refusal before child/postimage/delivery')
    preserved={}
    for name,kind in [('acceptance-probe.json','HERMES763_ACTUAL_TINY_PUBLIC_PROBE'),
                      ('acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND'),
                      ('acceptance-canary.json','HERMES763_ACTUAL_SYNCED_CANARY')]:
        v=t.load(control/name)
        p.require(v.get('status')=='DONE' and v.get('kind')==kind and v.get('code')==previous
                  and v.get('sourceBundleSha256')==owner['sourceBundleSha256'], 'unchanged actual successful prior checks')
        preserved[name]=p.signature(control/name)['sha256']
    p.require(not (Path(m['vault'])/CANARY_NAME).exists(),'completed canary remains removed')
    return {'kind':'HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION','namespace':t.NAMESPACE,
            'previousCode':previous,'initialGeneration':generation,'sourceBundleSha256':owner['sourceBundleSha256'],
            'claimSha256':p.signature(control/'acceptance-brief.json')['sha256'],
            'reservationSha256':p.signature(state/'writer-reservation.json')['sha256'],
            'preservedReceipts':preserved,'emptyRun':str(runs[0]),'journalPreimages':reservation['expected'],
            'provider':'NO_MODEL','process':'NOT_STARTED','vaultCommit':'NONE','delivery':'NOT_ATTEMPTED'}


def continue_brief(m, request):
    """One narrowly proven NO_EFFECT continuation from latest native state; never reimport NAS."""
    p.require(set(request)=={'freeze','sourceProof','peers'},'fresh continuation observations only')
    timed_window(request['freeze']); engineering=engineering_evidence(m); proof=brief_noeffect(m)
    state=Path(m['paths']['state']); control=state/'controller'; owner_path=control/'ownership.json'
    current=engineering_identity(m); previous=proof['previousCode']
    p.require(set(current)==set(previous) and {n for n in current if current[n]!=previous[n]}
              <= {'production-runtime.py','production-writers.py','production-module.nix','@metadata'},
              'only exact runtime/profile-exclusion and no-effect reservation correction')
    arming=t.load(control/'arming.json'); old_proof=arming['sourceProof']; actual=request['sourceProof']
    p.require(actual.get('running') is False and actual.get('pid')==0 and actual.get('restartPolicy')=='no'
              and actual.get('managedRetirement') is True and 0<=time.time()-actual.get('observedAt',0)<=30
              and all(actual.get(k)==old_proof.get(k) for k in ('containerID','imageID','revision','retirementSha256')),
              'fresh exact retained stopped NAS; no source credential read/replay')
    writer_module().peer_check(request['peers'],{},time.time())
    path=control/'acceptance-noeffect-continuation.json'
    p.require(not path.exists(),'one no-effect continuation only; unknown repeated incident needs review')
    archive=control/'acceptance-noeffect-archive'/proof['claimSha256']
    p.require(not archive.exists(),'preserve existing incident archive'); p.stage.mkdir(archive)
    for name in ('arming.json','acceptance-brief.json',*proof['preservedReceipts']):
        p.stage.atomic(archive/name,p.stage.read_private(control/name,owner=os.getuid()))
    p.stage.atomic(archive/'writer-reservation.json',p.stage.read_private(state/'writer-reservation.json',owner=os.getuid()))
    # Archive originals; do not clear or mark any work delivered. New brief claim
    # and reservation may supersede ONLY these exact retained no-effect hashes.
    proof.update(code=current,archive=str(archive),freeze=request['freeze'],sourceProof=actual,
                 engineeringSha256=p.signature(control/'engineering.json')['sha256'],recordedAt=time.time(),retentionDaysMinimum=14)
    before_owner=p.signature(owner_path); before_arm=p.signature(control/'arming.json')
    timed_window(request['freeze']); p.stage.atomic(path,p.stage.encoded(proof))
    arming.update(code=current,sourceProof=actual,freeze=request['freeze'],initialGeneration=proof['initialGeneration'],
                  noEffectContinuationSha256=p.signature(path)['sha256'])
    p.atomic_durable(control/'arming.json',p.stage.encoded(arming),before_arm)
    owner=t.load(owner_path); owner.update(phase='NATIVE_ARMED',poller='ENABLED',providerRefresh='ENABLED',
                                        scheduler='DISABLED',vaultWrites='ENABLED',continuedAt=time.time())
    p.atomic_durable(owner_path,p.stage.encoded(owner),before_owner)
    return {'namespace':t.NAMESPACE,'native':'NOT_STARTED','continuation':'PROVEN_NO_EFFECT',
            'preservedChecks':'PUBLIC_PROBE_INBOUND_CANARY_NOT_REPEATED','scheduler':'CLOSED','nasImport':'NOT_ATTEMPTED'}


def acceptance_brief(m, request, observe, *, send=None):
    """One actual reviewed zero-model daily write, convergence, and bot delivery."""
    state = Path(m['paths']['state'])
    with scheduler_transition(m):
        owner, arming = acceptance_context(m)
        p.require(set(request) == {'scope'}, 'fixed acceptance brief scope')
        recorded_acceptance(m, 'acceptance-inbound.json', 'HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND')
        recorded_acceptance(m, 'acceptance-canary.json', 'HERMES763_ACTUAL_SYNCED_CANARY')
        files = task_targets('morning-brief', [])
        writer_module().scope_check(request['scope'], files, time.time())
        path = state/'controller/acceptance-brief.json'
        before_claim=None
        if path.exists():
            review_path=state/'controller/acceptance-noeffect-continuation.json'
            p.require(review_path.exists(),'brief already claimed; uncertain write/delivery is never retried')
            review=t.load(review_path); before_claim=p.signature(path)
            p.require(review.get('kind')=='HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION'
                      and review.get('code')==arming['code'] and review.get('claimSha256')==before_claim['sha256']
                      and review.get('sourceBundleSha256')==owner['sourceBundleSha256']
                      and p.stage.read_private(Path(review['archive'])/'acceptance-brief.json',owner=os.getuid())
                          == p.stage.read_private(path,owner=os.getuid()),
                      'brief already claimed; only exact proven pre-process no-effect continuation')
        receipt = {'schemaVersion': 1, 'namespace': t.NAMESPACE, 'status': 'CLAIMED',
                   'kind': 'HERMES763_ACTUAL_ZERO_MODEL_BRIEF', 'claimedAt': time.time(),
                   'sourceBundleSha256': owner['sourceBundleSha256'], 'code': arming['code'],
                   'files': list(files), 'provider': 'NO_MODEL', 'retentionDaysMinimum': 14}
        if before_claim is not None:
            receipt['reconciledNoEffectClaimSha256']=before_claim['sha256']
        p.atomic_durable(path, p.stage.encoded(receipt), before_claim); before = p.signature(path)
        result = maintenance_task(m, {'task': 'morning-brief', 'args': [], 'scope': request['scope']}, observe)
        output = base64.b64decode(result['outputBase64'], validate=True)
        p.stage.atomic(state/'controller/acceptance-brief.stdout', output)
        p.require(result['task'] == 'COMPLETE' and result['provider'] == 'NO_MODEL', 'actual brief adapter completion')
        acceptance_context(m)
        chat = t.load(state/'.secrets.json')['TELEGRAM_HOME_CHANNEL']
        response = (send or telegram_send_once)(m, chat, output.decode('utf-8'))
        p.require(response.get('ok') is True and response.get('result', {}).get('message_id') is not None
                  and str(response['result'].get('chat', {}).get('id')) == chat,
                  'actual brief delivery acknowledgement; uncertainty is not retried')
        acceptance_context(m)
        receipt.update(status='DONE', completedAt=time.time(), outputSha256=p.stage.digest(output),
                       postimages=writer_module().manifest(Path(m['vault']), files),
                       deliveryMessageID=str(response['result']['message_id']),
                       convergence='ACTUAL_ALL_PEER_METADATA')
        p.atomic_durable(path, p.stage.encoded(receipt), before)
        return {'namespace': t.NAMESPACE, 'realZeroModelBrief': 'DONE', 'delivery': 'ACKNOWLEDGED_ONCE'}


ACCEPTANCE_KINDS=(('acceptance-probe.json','HERMES763_ACTUAL_TINY_PUBLIC_PROBE'),
                  ('acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND'),
                  ('acceptance-canary.json','HERMES763_ACTUAL_SYNCED_CANARY'),
                  ('acceptance-brief.json','HERMES763_ACTUAL_ZERO_MODEL_BRIEF'))


def previous_final_gate(m, review, arming):
    """Audit the actual immutable failed generation, not an operator PASS claim."""
    control=Path(m['paths']['state'])/'controller'; sha=review['engineeringSha256']
    path=control/'engineering.json'
    if p.signature(path)['sha256']!=sha:
        path=control/'engineering-runs/ready-history'/(sha+'.json')
    p.require(p.signature(path)['sha256']==sha,'exact retained pre-final-gate engineering receipt')
    previous=t.load(path); generation=Path(previous['installedGeneration'])
    p.require(previous.get('kind')=='HERMES763_ACTUAL_PRESTOP_ENGINEERING' and previous.get('productionReady') is True
              and all(previous.get(k)=='PASS' for k in ['runtimeGuard','coldImport','reverseRecovery','writerGate',
                                                        'nasRedeployGuard','sourceProfileCAS','syncthingConvergence']),
              'retained actual complete engineering provenance; focused final correction only')
    p.require(str(generation).startswith('/nix/store/') and generation.name.endswith('-home-manager-generation')
              and previous.get('code')==arming['code']==review.get('code'), 'original failed immutable gate identity')
    metadata=(generation/'home-files/.config/hermes-native/production.json').resolve(strict=True)
    p.require(str(metadata).startswith('/nix/store/'),'immutable original final-gate metadata')
    old=json.loads(metadata.read_bytes()); identity=engineering_identity(old)
    text=(Path(old['managedAssets'])/'production-runtime.py').read_text()
    p.require(identity==arming['code'] and old['python']==m['python'] and old['revision']==m['revision']
              and old['environment']['TZ']==m['environment']['TZ']=='America/New_York'
              and "p.require(schedule=={'kind':'cron','expr':'0 5 * * *'},'one original NY daily schedule')" in text,
              'exact canonical-display strict-equality defect in original immutable code')
    return str(generation)


def final_gate_ready(m):
    """Read-only exact completed-acceptance/final-schedule incident qualification."""
    check(m); t.native_stopped(m)
    state=Path(m['paths']['state']); control=state/'controller'
    owner=t.load(control/'ownership.json'); arming=t.load(control/'arming.json')
    review=t.load(control/'acceptance-noeffect-continuation.json')
    p.require(owner.get('phase')=='STOPPED_REVIEW_REQUIRED' and arming.get('status')=='ARMED'
              and not (control/'initial-acceptance.json').exists()
              and review.get('kind')=='HERMES763_PROFILE_SYMLINK_NO_EFFECT_CONTINUATION'
              and owner['sourceBundleSha256']==arming['sourceBundleSha256']==review.get('sourceBundleSha256'),
              'only exact revoked pre-live canonical-display incident; no partial initial transition')
    original_arming=dict(arming)
    final_path=control/'acceptance-final-gate-continuation.json'
    prior_final=t.load(final_path) if final_path.exists() else None
    if prior_final:
        p.require(prior_final.get('kind')=='HERMES763_CANONICAL_DISPLAY_FINAL_GATE_CONTINUATION'
                  and prior_final.get('code')==arming['code']
                  and prior_final.get('sourceBundleSha256')==owner['sourceBundleSha256']
                  and p.signature(state/'cron/jobs.json')['sha256']==prior_final.get('jobsSha256')
                  and p.signature(state/'writer-reservation.json')['sha256']==prior_final.get('reservationSha256'),
                  'exact failed final metadata-only activation with no scheduler/reservation effect')
        original_arming['code']=prior_final['previousCode']
    generation=previous_final_gate(m,review,original_arming)
    current=engineering_identity(m); previous=original_arming['code']
    p.require(set(current)==set(previous) and {n for n in current if current[n]!=previous[n]}
              <= {'production-runtime.py','production-transfer.py','production-module.nix','@metadata'},
              'only final canonical-display/retained-receipt and identical reverse-schedule guard correction')
    preserved={}; codes={}
    for name,kind in ACCEPTANCE_KINDS:
        receipt,sha=retained_acceptance(m,name,kind,owner,arming)
        preserved[name]=sha; codes[name]=receipt['code']
        if name=='acceptance-brief.json':
            p.require(receipt.get('provider')=='NO_MODEL'
                      and receipt.get('files')==list(task_targets('morning-brief',[]))
                      and receipt.get('convergence')=='ACTUAL_ALL_PEER_METADATA'
                      and receipt.get('deliveryMessageID') is not None
                      and p.signature(control/'acceptance-brief.stdout')['sha256']==receipt.get('outputSha256')
                      and writer_module().manifest(Path(m['vault']),receipt['files'])==receipt['postimages'],
                      'completed real brief/output/delivery/postimage required; never repeat')
            reservation=t.load(state/'writer-reservation.json')
            p.require(reservation.get('status')=='COMPLETE'
                      and reservation.get('postimages')==receipt['postimages'],
                      'actual completed brief reservation unchanged')
    p.require(not (Path(m['vault'])/CANARY_NAME).exists(),'completed canary remains absent')
    jobs=t.load(state/'cron/jobs.json')
    source=json.loads(t.decode_bundle(t.load(Path(t.load(control/'import.json')['sourceBundle'])))['cron/jobs.json'])
    canonical={'kind':'cron','expr':'0 5 * * *','display':'0 5 * * *'}
    p.require(len(jobs['jobs'])==len(source['jobs'])==1 and jobs['jobs'][0]['id']==source['jobs'][0]['id']
              and jobs['jobs'][0]['schedule']==source['jobs'][0]['schedule']==canonical
              and jobs['jobs'][0]['enabled'] is False and jobs['jobs'][0]['no_agent'] is True
              and jobs['jobs'][0]['state']=='paused','exact retained closed source NY daily schedule identity')
    next_run=next_distinct_brief(jobs['jobs'][0]['schedule'])
    return {'kind':'HERMES763_CANONICAL_DISPLAY_FINAL_GATE_CONTINUATION','namespace':t.NAMESPACE,
            'previousGeneration':generation,'previousCode':previous,'code':current,
            'sourceBundleSha256':owner['sourceBundleSha256'],'preservedReceipts':preserved,'receiptCodes':codes,
            'jobsSha256':p.signature(state/'cron/jobs.json')['sha256'],
            'reservationSha256':p.signature(state/'writer-reservation.json')['sha256'],
            'nextDistinctBrief':next_run,'acceptance':'ALL_FOUR_DONE_NOT_REPEATED','retentionDaysMinimum':14}


FINAL_GATE_CASES=('Transfer.test_initial_live_is_not_final_acceptance_and_uses_pinned_ny_schedule',
                  'Transfer.test_preserved_canonical_schedule_display_passes_without_rewriting_or_weakening_daily_guard',
                  'Transfer.test_final_only_continuation_preserves_all_done_receipts_and_rejects_partial_or_drift')


def final_gate_evidence(m):
    """Current focused final controller proof, not another broad readiness replay."""
    check(m); state=Path(m['paths']['state']); control=state/'controller'
    code=engineering_identity(m); receipt=t.load(control/'final-gate-evidence.json')
    generation=Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)
    p.require(receipt.get('kind')=='HERMES763_ACTUAL_FOCUSED_FINAL_GATE' and receipt.get('code')==code
              and receipt.get('installedGeneration')==str(generation) and receipt.get('cases')==list(FINAL_GATE_CASES)
              and receipt.get('returnCode')==0 and 0<=time.time()-receipt.get('recordedAt',0)<=600
              and receipt.get('fixtureSha256')==p.stage.digest(p.stage.read_private(Path(m['productionFixture']))),
              'fresh actual immutable focused final-gate cases required')
    provider=t.load(control/'engineering-providers.json')
    p.require(provider.get('kind')=='HERMES763_ACTUAL_READONLY_PROVIDER_EVIDENCE'
              and provider.get('code')==code and provider.get('installedGeneration')==str(generation)
              and set(provider.get('reports',{}))=={'get-calendar','get-weather'}
              and all(v.get('status')=='PASS' and 0<=time.time()-v.get('observedAt',0)<=600
                      and p.stage.digest(p.stage.read_private(Path(provider['retained'])/(n+'.stdout')))==v.get('outputSha256')
                      for n,v in provider['reports'].items()),'fresh actual read-only Calendar/weather evidence')
    source=Path('/home/johna/dev/src/system-config-amfaro')
    p.require(all(p.stage.digest(p.stage.read_private(source/'modules/home-manager/hermes-native'/n,owner=os.getuid()))==sha
                  for n,sha in code.items() if not n.startswith('@')),'current scoped source/immutable code CAS')
    prior=t.load(control/'engineering.json')
    p.require(p.stage.digest(p.stage.read_private(source/'flake.lock',owner=os.getuid()))==prior['sourceHashes']['@flake.lock'],
              'independent source lock unchanged')
    ledger=t.load(control/'task-code.json')
    p.require(ledger.get('files')==prior.get('taskCode') and all(
              p.stage.digest(p.stage.read_private(Path(m['vault'])/n,owner=os.getuid()))==sha
              for n,sha in ledger['files'].items()),'unchanged actual reviewed deterministic task code')
    return receipt


def focused_final_gate(m):
    proof=final_gate_ready(m); state=Path(m['paths']['state']); code=engineering_identity(m)
    fixture=Path(m['productionFixture']); p.require(str(fixture).startswith('/nix/store/'),'actual immutable focused fixture')
    fixture_assets=fixture.parent.parent/'modules/home-manager/hermes-native'
    p.require(all(p.stage.digest(p.stage.read_private(fixture_assets/n))==sha for n,sha in code.items()
                  if not n.startswith('@')),'actual focused fixture uses exact installed asset bytes')
    root=Path(tempfile.mkdtemp(prefix='focused-final-gate-',dir=state/'controller/engineering-runs')); root.chmod(0o700)
    env=dict(m['environment'],HERMES763_TASK_SOURCES='FOCUSED_CRON_CASES_USE_SYNTHETIC_PAYLOADS_ONLY')
    harness="import importlib.util,unittest,sys,json; s=importlib.util.spec_from_file_location('f',sys.argv[1]); f=importlib.util.module_from_spec(s); s.loader.exec_module(f); suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[2:],f); result=unittest.TextTestRunner(stream=sys.stderr).run(suite); print(json.dumps({'testsRun':result.testsRun,'skipped':len(result.skipped),'errors':len(result.errors),'failures':len(result.failures)})); sys.exit(0 if result.wasSuccessful() and not result.skipped and result.testsRun==3 else 1)"
    run=subprocess.run([m['python'],'-I','-B','-c',harness,str(fixture),*FINAL_GATE_CASES],
                       cwd='/',env=env,capture_output=True,timeout=90)
    p.stage.atomic(root/'stdout',run.stdout); p.stage.atomic(root/'stderr',run.stderr)
    p.require(run.returncode==0,'actual focused final-gate cases failed; private retained evidence')
    report=json.loads(run.stdout); p.require(report=={'testsRun':3,'skipped':0,'errors':0,'failures':0},'all three actual focused cases executed')
    receipt={'kind':'HERMES763_ACTUAL_FOCUSED_FINAL_GATE','namespace':t.NAMESPACE,'code':code,
             'installedGeneration':str(Path('/home/johna/.local/state/nix/profiles/home-manager').resolve(strict=True)),
             'cases':list(FINAL_GATE_CASES),'returnCode':0,'fixtureSha256':p.stage.digest(p.stage.read_private(fixture)),
             'recordedAt':time.time(),'retained':str(root),'retentionDaysMinimum':14}
    p.stage.atomic(state/'controller/final-gate-evidence.json',p.stage.encoded(receipt)); final_gate_evidence(m)
    return {'namespace':t.NAMESPACE,'finalGate':'PROVEN_READY','acceptance':proof['acceptance'],
            'nextDistinctBrief':proof['nextDistinctBrief'],'native':'STOPPED','focusedTests':3,
            'providers':'ACTUAL_READ_ONLY_PASS','retained':str(root),'vaultMutationOrDelivery':'NONE'}


def continue_live(m, request):
    """Final activation only, from latest native state and all four DONE receipts."""
    p.require(set(request)=={'sourceProof','peers'},'fresh final-only observations; no vault mutation or human freeze')
    final_gate_evidence(m)
    state=Path(m['paths']['state']); control=state/'controller'
    with scheduler_transition(m), writer_module().held_lock(state/'cron/.jobs.lock'):
        proof=final_gate_ready(m); arming=t.load(control/'arming.json'); old=arming['sourceProof']; actual=request['sourceProof']
        p.require(actual.get('running') is False and actual.get('pid')==0 and actual.get('restartPolicy')=='no'
                  and actual.get('managedRetirement') is True and 0<=time.time()-actual.get('observedAt',0)<=30
                  and all(actual.get(k)==old.get(k) for k in ('containerID','imageID','revision','retirementSha256')),
                  'fresh exact retained stopped NAS for final-only activation')
        writer_module().peer_check(request['peers'],{},time.time())
        archive=control/'acceptance-final-gate-archive'/proof['preservedReceipts']['acceptance-brief.json']
        before_owner=p.signature(control/'ownership.json'); before_arm=p.signature(control/'arming.json')
        owner=t.load(control/'ownership.json')
        if archive.exists():
            prior=t.load(control/'acceptance-final-gate-continuation.json')
            p.require(prior.get('archive')==str(archive) and prior.get('preservedReceipts')==proof['preservedReceipts']
                      and not (archive/'failed-final-gate.json').exists()
                      and all(p.stage.read_private(archive/n,owner=os.getuid())==p.stage.read_private(control/n,owner=os.getuid())
                              for n in proof['preservedReceipts']),
                      'only exact contained failed supervisor-path activation; no acceptance work replay')
            p.stage.atomic(archive/'failed-final-gate.json',p.stage.read_private(control/'acceptance-final-gate-continuation.json',owner=os.getuid()))
            p.stage.atomic(archive/'failed-final-arming.json',p.stage.read_private(control/'arming.json',owner=os.getuid()))
        else:
            for name in ('arming.json',*proof['preservedReceipts']):
                raw=p.stage.read_private(control/name,owner=os.getuid())
                if name!='arming.json': p.require(p.stage.digest(raw)==proof['preservedReceipts'][name],'completed receipt CAS')
                p.stage.atomic(archive/name,raw)
            p.stage.atomic(archive/'writer-reservation.json',p.stage.read_private(state/'writer-reservation.json',owner=os.getuid()))
        p.require(p.signature(state/'cron/jobs.json')['sha256']==proof['jobsSha256']
                  and p.signature(state/'writer-reservation.json')['sha256']==proof['reservationSha256'],
                  'closed scheduler/completed reservation CAS')
        final_gate_evidence(m)
        proof.update(archive=str(archive),sourceProof=actual,recordedAt=time.time(),
                     focusedEvidenceSha256=p.signature(control/'final-gate-evidence.json')['sha256'])
        path=control/'acceptance-final-gate-continuation.json'; p.stage.atomic(path,p.stage.encoded(proof))
        arming.update(code=proof['code'],sourceProof=actual,
                      finalGateContinuationSha256=p.signature(path)['sha256'])
        p.atomic_durable(control/'arming.json',p.stage.encoded(arming),before_arm)
        owner.update(phase='NATIVE_ARMED',poller='ENABLED',providerRefresh='ENABLED',vaultWrites='ENABLED',
                     scheduler='DISABLED',finalGateContinuedAt=time.time())
        p.atomic_durable(control/'ownership.json',p.stage.encoded(owner),before_owner)
    return {'namespace':t.NAMESPACE,'continuation':'FINAL_ACTIVATION_ONLY','native':'NOT_STARTED',
            'acceptance':'ALL_FOUR_DONE_NOT_REPEATED','scheduler':'CLOSED','nasImport':'NOT_ATTEMPTED'}


def initial_live(m, acceptance):
    """Transition while the sole gateway holds runtime.lock, never bypass it."""
    state=Path(m['paths']['state'])
    with scheduler_transition(m), writer_module().held_lock(state/'cron/.jobs.lock'):
        # Same exact jobs flock as pinned upstream, but ours fails closed instead
        # of its timeout/degraded-lock fallback. Tick is gated before claims.
        return _initial_live_locked(m,acceptance)


def next_distinct_brief(schedule, now=None):
    """Acceptance delivered today's daily: next automatic send is a new daily."""
    from cron.jobs import compute_next_run
    p.require(schedule in ({'kind':'cron','expr':'0 5 * * *'},
                           {'kind':'cron','expr':'0 5 * * *','display':'0 5 * * *'}),
              'one original NY daily schedule')
    now=now or datetime.now(ZoneInfo('America/New_York'))
    anchor=max(now,now.replace(hour=5,minute=0,second=0,microsecond=0))
    result=compute_next_run(schedule,anchor.isoformat())
    p.require(result,'supported next distinct daily schedule required')
    return result


def _initial_live_locked(m, acceptance):
    """Initial success is native live/observation pending, never final acceptance."""
    state=Path(m['paths']['state']); path=state/'controller/ownership.json'; owner=live_owner(m,'poller')
    p.require(owner['phase']=='NATIVE_ARMED','initial one-time observation transition')
    _, arming=acceptance_context(m)
    if arming.get('finalGateContinuationSha256'):
        p.require(set(acceptance)=={'sourceProof','peers'},'final-only controller observations; no vault mutation or human freeze')
    else:
        p.require(set(acceptance)=={'sourceProof','peers','freeze'}, 'actual final ownership observations only; no PASS flags')
        timed_window(acceptance['freeze'])
    writer_module().peer_check(acceptance['peers'], {}, time.time())
    proof=acceptance['sourceProof']; original=arming['sourceProof']
    p.require(proof.get('running') is False and proof.get('pid')==0 and proof.get('restartPolicy')=='no'
              and proof.get('managedRetirement') is True and 0<=time.time()-proof.get('observedAt',0)<=30
              and all(proof.get(k)==original.get(k) for k in ['imageID','containerID','retirementSha256','revision']),
              'fresh actual sole stopped NAS ownership proof')
    row=dict(q.split('=',1) for q in systemctl('show',m['service'],'-p','ActiveState','-p','MainPID','-p','Restart').decode().splitlines() if '=' in q)
    p.require(row.get('ActiveState')=='active' and int(row.get('MainPID','0'))>0 and row.get('Restart')=='no',
              'actual sole native foreground service required')
    pid=int(row['MainPID'])
    command=Path('/proc/'+str(pid)+'/cmdline').read_bytes().split(b'\x00')
    operator=Path(m['operator'])
    p.require(str(operator).startswith('/nix/store/') and str(operator).encode() in command and b'gateway' in command
              and p.stage.digest(p.stage.read_private(operator))==engineering_identity(m)['production-runtime.py'],
              'actual exact immutable managed supervisor process and reviewed source bytes')
    stage_row=dict(q.split('=',1) for q in systemctl('show','hermes-native.service','-p','ActiveState','-p','MainPID').decode().splitlines() if '=' in q)
    p.require(stage_row.get('ActiveState')=='inactive' and stage_row.get('MainPID')=='0', 'staging remains inactive')
    identities={}
    for name,kind in [('acceptance-probe.json','HERMES763_ACTUAL_TINY_PUBLIC_PROBE'),
                      ('acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND'),
                      ('acceptance-canary.json','HERMES763_ACTUAL_SYNCED_CANARY'),
                      ('acceptance-brief.json','HERMES763_ACTUAL_ZERO_MODEL_BRIEF')]:
        receipt,sha=recorded_acceptance(m,name,kind); identities[name]=sha
        if name=='acceptance-brief.json':
            p.require(writer_module().manifest(Path(m['vault']),receipt['files'])==receipt['postimages'],
                      'actual acceptance brief postimage drift; preserve both branches')
    acceptance={'schemaVersion':1,'namespace':t.NAMESPACE,'kind':'HERMES763_ACTUAL_INITIAL_ACCEPTANCE',
                'sourceBundleSha256':owner['sourceBundleSha256'],'code':arming['code'],
                'receipts':identities,'sourceProof':proof,'nativeSupervisorPID':pid,
                'completedAt':time.time(),'retentionDaysMinimum':14,'observation':'PENDING'}
    expected=p.signature(path)
    jobs_path=state/'cron/jobs.json'; jobs=t.load(jobs_path); before=p.signature(jobs_path)
    source_jobs=json.loads(t.decode_bundle(t.load(Path(t.load(state/'controller/import.json')['sourceBundle'])))['cron/jobs.json'])
    p.require(len(jobs['jobs'])==len(source_jobs['jobs'])==1
              and jobs['jobs'][0]['id']==source_jobs['jobs'][0]['id']
              and jobs['jobs'][0]['enabled'] is False and jobs['jobs'][0]['no_agent'] is True,'one closed zero-model scheduler with retained source identity')
    job=jobs['jobs'][0]
    # Use pinned upstream schedule calculation; no duplicate timer/scheduler.
    job.update(enabled=True,state='scheduled',paused_reason=None,deliver='telegram',failure_deliver='telegram')
    # The actual acceptance brief already delivered today's daily. Starting
    # before 05:00 must not deliver that same daily again at 05:00.
    job['next_run_at']=next_distinct_brief(job['schedule'])
    p.require(job['next_run_at'],'actual next distinct daily 05:00 NY brief schedule')
    acceptance['scheduledAcceptanceDayReplay']='SUPPRESSED_ALREADY_DELIVERED'
    p.stage.atomic(state/'controller/initial-acceptance.json',p.stage.encoded(acceptance))
    p.atomic_durable(jobs_path,p.stage.encoded(jobs),before)
    owner.update(phase='NATIVE_LIVE',scheduler='ENABLED',liveAt=time.time(),observationStatus='PENDING',
                 observationMinimumHours=24,nextScheduledBriefRequired=True)
    p.atomic_durable(path,p.stage.encoded(owner),expected)
    return {'status':'native live/observation pending','namespace':t.NAMESPACE,'nextBrief':job['next_run_at'],
            'minimumObservationHours':24,'finalAcceptance':False}


def stop(m):
    """Revoke native capabilities FIRST, then contain the exact managed service.

    This route never resumes NAS, changes vault bytes, clears journals or resets
    ownership. It is safe containment, not data recovery or generic systemd access.
    """
    owner_path = Path(m['paths']['state'])/'controller/ownership.json'
    expected = p.signature(owner_path)
    owner = t.load(owner_path)
    p.require(owner.get('schemaVersion') == 1 and owner.get('namespace') == t.NAMESPACE
              and owner.get('owner') == 'native'
              and owner.get('phase') in {'NATIVE_ARMED','NATIVE_LIVE','STOPPED_REVIEW_REQUIRED'},
              'only native-owned production can be revoked; NAS/CLOSED remains untouched')
    owner.update(phase='STOPPED_REVIEW_REQUIRED',poller='DISABLED',scheduler='DISABLED',
                 vaultWrites='DISABLED',providerRefresh='DISABLED',revokedAt=time.time())
    p.atomic_durable(owner_path,p.stage.encoded(owner),expected)
    subprocess.run(['/usr/bin/systemctl','--user','stop','hermes-production.service'],
                   capture_output=True,check=True,
                   env={'PATH':'/usr/bin:/bin','LANG':'C','XDG_RUNTIME_DIR':'/run/user/1000',
                        'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/1000/bus'})
    proof = t.native_stopped(m)
    return {'namespace':t.NAMESPACE,'ownership':'REVOKED','native':proof,
            'nas':'NOT_RESUMED','vaultRestore':'NOT_PERFORMED','journals':'RETAINED'}


def main():
    p.require(len(sys.argv)==2,'fixed production operation required')
    operation = sys.argv[1]
    m = t.native_metadata()
    if operation == 'initialize':
        result = initialize(m)
    elif operation == 'check':
        result = check(m)
    elif operation == 'stop':
        result = stop(m)
    elif operation == 'engineering-evidence':
        result = engineering_evidence(m)
    elif operation == 'incident-status':
        result = t.native_stopped(m)
    elif operation in {'engineering-components','engineering-providers','engineering-ready'}:
        limit=4*1024*1024 if operation=='engineering-ready' else 65536
        raw=sys.stdin.buffer.read(limit+1); p.require(len(raw)<=limit,'bounded fixed engineering input')
        handler={'engineering-components':engineering_components,'engineering-providers':engineering_providers,
                 'engineering-ready':engineering_ready}[operation]
        result=handler(m,json.loads(raw))
    elif operation == 'brief-noeffect':
        proof=brief_noeffect(m)
        result={'namespace':t.NAMESPACE,'noEffect':'PROVEN','proofSha256':p.stage.digest(p.stage.encoded(proof)),
                'initialGeneration':proof['initialGeneration'],'process':proof['process'],
                'vaultCommit':proof['vaultCommit'],'delivery':proof['delivery']}
    elif operation == 'final-gate-ready':
        result=focused_final_gate(m)
    elif operation in {'arm','initial-live','continue-brief','continue-live'}:
        raw=sys.stdin.buffer.read(65537); p.require(len(raw)<=65536,'bounded operator evidence')
        request=json.loads(raw)
        if operation in {'arm','continue-brief','continue-live'}:
            with writer_module().held_lock(Path(m['paths']['state'])/'controller/runtime.lock'):
                result={'arm':arm,'continue-brief':continue_brief,'continue-live':continue_live}[operation](m,request)
        else:
            result=initial_live(m,request)
    elif operation == 'public-probe':
        result=public_probe(m)
    elif operation == 'public-probe-child':
        public_probe_child(m); return
    elif operation == 'start':
        result=start(m)
    elif operation == 'gateway':
        gateway(m); return
    elif operation == 'gateway-child':
        gateway_child(m); return
    elif operation == 'acceptance-status':
        state=Path(m['paths']['state']); acceptance_context(m)
        path=state/'controller/acceptance-inbound.json'
        if path.exists():
            recorded_acceptance(m,'acceptance-inbound.json','HERMES763_ACTUAL_INBOUND_ZERO_MODEL_COMMAND')
            result={'namespace':t.NAMESPACE,'actualInboundZeroModelCommand':'DONE'}
        else:
            result={'namespace':t.NAMESPACE,'actualInboundZeroModelCommand':'PENDING'}
    elif operation in {'maintenance-task','acceptance-canary','acceptance-brief'}:
        raw=sys.stdin.buffer.readline(65537); p.require(len(raw)<=65536,'bounded maintenance input')
        request=json.loads(raw)
        def observe(names):
            print(json.dumps({'request':'OBSERVE_ACTUAL_PEERS','files':list(names)}),flush=True)
            raw=sys.stdin.buffer.readline(65537); p.require(len(raw)<=65536,'bounded actual peer metadata')
            return json.loads(raw)
        if operation=='maintenance-task':
            result=maintenance_task(m,request,observe)
        else:
            try:
                result=(acceptance_canary if operation=='acceptance-canary' else acceptance_brief)(m,request,observe)
            except BaseException:
                current=t.load(Path(m['paths']['state'])/'controller/ownership.json')
                if current.get('owner')=='native' and current.get('phase')=='NATIVE_ARMED': stop(m)
                raise
    elif operation == 'brief-request':
        live_owner(m,'scheduler')
        observe,scan=local_writer_callbacks(m)
        sys.stdout.buffer.write(sandboxed_task(m,'morning-brief',[],observer=observe,scan=scan)); return
    elif operation == 'import':
        raw = sys.stdin.buffer.read(p.MAX_TOTAL*2+1)
        p.require(len(raw)<=p.MAX_TOTAL*2,'bounded private transfer')
        spec = importlib.util.spec_from_file_location('production_writers',Path(__file__).with_name('production-writers.py'))
        w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
        with w.held_lock(Path(m['paths']['state'])/'controller/runtime.lock'):
            result = t.import_bundle(json.loads(raw),m)
    elif operation == 'incident-export':
        # Private stream ONLY; do not run without the operator's private sink.
        sys.stdout.buffer.write(p.stage.encoded(t.incident_export(m)))
        return
    else:
        raise ValueError('runtime/polling/scheduling/writes/restore are closed')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError,TypeError,json.JSONDecodeError,subprocess.SubprocessError) as e:
        print('REFUSED production runtime: '+type(e).__name__,file=sys.stderr)
        raise SystemExit(64)
