#!/usr/bin/env python3
"""#771 explicit ONE-TIME reviewed packaging adoption, never automatic resume.

Use --qualify for read-only review. --adopt needs John's fresh window plus actual
source/peer observations. Preserves original receipts, current state and jobs;
any failure after containment leaves the native owner stopped for review.
"""
import argparse
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import tempfile
from datetime import datetime

spec = importlib.util.spec_from_file_location('lifecycle', Path(__file__).with_name('hermes-activation-check.py'))
l = importlib.util.module_from_spec(spec)
spec.loader.exec_module(l)
DATABASES = ('state.db', 'shared-state.db', 'kanban.db', 'response_store.db',
             'runs_idempotency.db', 'cron/notepad.db', 'cron/executions.db')
POINTERS = ('managedAssets', 'launcher', 'operator', 'transferOperator', 'productionFixture', 'writerFixture')
ENV_POINTERS = ('HERMES_NATIVE_ASSETS', 'HERMES_PRODUCTION_OPERATOR')
WRITERS = {'gateway', 'brief', 'omarchy-tasks', 'mac-tasks', 'editors', 'mobile-icloud'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def metadata(generation):
    return l.immutable_json(generation / 'home-files/.config/hermes-native/production.json')


def module_diff(old_code, new_code):
    changed = {k for k in set(old_code) | set(new_code) if old_code.get(k) != new_code.get(k)}
    l.require(changed == {'@metadata', 'production-module.nix'}
              and old_code.get('production-module.nix') == l.OLD_MODULE_SHA
              and new_code.get('production-module.nix') == l.NEW_MODULE_SHA,
              'only exact reviewed initial packaging module/metadata change permitted')


def equivalent(old, new, old_unit, new_unit):
    """Compare explicit pointer fields and the actual immutable bytes they bind.

    Not a general store-hash normalizer: every other metadata/unit/launcher byte
    must be identical. The new Nix module itself has fixed reviewed preimages.
    """
    expected = copy.deepcopy(old)
    replacements = {}
    for key in POINTERS:
        replacements[old[key]] = new[key]
        expected[key] = new[key]
    for key in ENV_POINTERS:
        replacements[old['environment'][key]] = new['environment'][key]
        expected['environment'][key] = new['environment'][key]
    l.require(expected == new, 'semantic metadata change is outside packaging adoption')
    for key in ('operator', 'transferOperator', 'productionFixture', 'writerFixture'):
        l.require(Path(old[key]).read_bytes() == Path(new[key]).read_bytes(), 'changed executable/fixture bytes')
    for m in (old, new):
        sibling = Path(m['productionFixture']).with_name('hermes-native-production-state.py')
        l.require(sibling.is_file(), 'actual installed fixture sibling required')
    l.require(Path(old['productionFixture']).with_name('hermes-native-production-state.py').read_bytes()
              == Path(new['productionFixture']).with_name('hermes-native-production-state.py').read_bytes(),
              'changed state fixture bytes')
    launcher = Path(old['launcher']).read_bytes()
    for before, after in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        launcher = launcher.replace(before.encode(), after.encode())
    l.require(launcher == Path(new['launcher']).read_bytes(), 'semantic launcher change')
    translated_unit = old_unit
    for before, after in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        translated_unit = translated_unit.replace(before.encode(), after.encode())
    l.require(translated_unit == new_unit, 'semantic unit change')


def qualify(home, candidate):
    old_generation = (home / '.local/state/nix/profiles/home-manager').resolve(strict=True)
    old, new = metadata(old_generation), metadata(candidate)
    l.require(l.preflight(home, old_generation) == 'UNCHANGED_LIVE_IDENTITY', 'exact current live binding required')
    state = Path(old['paths']['state'])
    owner = l.private_json(state / 'controller/ownership.json')
    l.require(owner.get('phase') == 'NATIVE_LIVE' and all(owner.get(k) == 'ENABLED' for k in l.CAPABILITIES)
              and not owner.get('packagingAdoptionEvidence'), 'one-time live packaging adoption only')
    old_code, new_code = l.identity(old), l.identity(new)
    module_diff(old_code, new_code)
    equivalent(old, new,
               (old_generation / 'home-files/.config/systemd/user' / l.SERVICE).read_bytes(),
               (candidate / 'home-files/.config/systemd/user' / l.SERVICE).read_bytes())
    return old_generation, old, new, old_code, new_code


def no_uncertain_work(state):
    with sqlite3.connect('file:' + str(state / 'state.db') + '?mode=ro', uri=True) as db:
        counts = {table: db.execute('SELECT count(*) FROM ' + table).fetchone()[0]
                  for table in ('gateway_heartbeats', 'compression_locks', 'session_turn_leases', 'async_delegations')}
        deliveries = dict(db.execute('SELECT state,count(*) FROM delivery_obligations GROUP BY state'))
    l.require(not any(counts.values()) and set(deliveries) <= {'delivered'}, 'active/uncertain work; never replay')
    l.require(l.private_json(state / 'writer-reservation.json').get('status') == 'COMPLETE',
              'completed writer reservation required')
    l.require(not l.private_json(state / 'controller/pending-ingress.json').get('result'), 'pending ingress requires review')
    jobs = l.private_json(state / 'cron/jobs.json').get('jobs', [])
    l.require(len(jobs) == 1 and jobs[0].get('enabled') is True and jobs[0].get('no_agent') is True
              and datetime.fromisoformat(jobs[0]['next_run_at']).timestamp() > time.time() + 600,
              'preserved distinct future brief required; never replay overdue work')
    return {'leases': counts, 'deliveryStates': deliveries, 'writerReservation': 'COMPLETE',
            'nextDistinctBrief': jobs[0]['next_run_at']}


def observations(request):
    now = time.time()
    freeze = request['freeze']
    l.require(request.get('authorization') == 'JOHN_APPROVED_771_CONTROLLED_PACKAGING_ADOPTION'
              and request.get('userApproval') == 'ok, proceed'
              and freeze.get('manualConfirmationSource') == 'JOHN_EXECUTION_WINDOW'
              and freeze.get('coordinator') == 'omarchy' and set(freeze.get('excludedWriters', [])) == WRITERS
              and freeze.get('confirmedAt', 0) <= now < freeze.get('expiresAt', 0)
              and 0 < freeze['expiresAt'] - freeze['confirmedAt'] <= 600, 'fresh John-approved bounded window required')
    source = request['source']
    l.require(0 <= now - request['sourceObservedAt'] <= 30
              and source.get('kind') == 'HERMES763_NAS_BASELINE'
              and source.get('running') is False and source.get('pid') == 0
              and source.get('restartPolicy') == 'no' and source.get('retirementPresent') is True,
              'fresh actually stopped/protected NAS required')
    peers = request['peers']['peers']
    l.require(set(peers) == {'mac', 'nas', 'omarchy'}, 'actual three-peer observation required')
    topology = {'mac': {'nas', 'omarchy'}, 'nas': {'mac'}, 'omarchy': {'mac'}}
    for name, row in peers.items():
        l.require(0 <= now - row['observedAt'] <= 30 and row['state'] == 'idle'
                  and row['paused'] is False and row['completion'] == 100
                  and all(row.get(k) == 0 for k in ('needItems', 'needBytes', 'errors', 'pullErrors'))
                  and row.get('conflicts') == [] and set(row['connectedPeers']) == topology[name],
                  'fresh clean connected peer metadata required; not a content-hash or distributed lock proof')


def controller(old):
    spec = importlib.util.spec_from_file_location('original_runtime', Path(old['managedAssets']) / 'production-runtime.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def adopt(home, candidate, request):
    os.umask(0o077)
    original_generation, old, new, old_code, new_code = qualify(home, candidate)
    observations(request)
    state = Path(old['paths']['state'])
    r = controller(old)
    staging = r.systemctl('show', 'hermes-native.service', '-p', 'ActiveState', '-p', 'MainPID')
    l.require(b'ActiveState=inactive' in staging and b'MainPID=0' in staging, 'staging must remain inactive')
    no_uncertain_work(state)
    with r.scheduler_transition(old), r.writer_module().held_lock(state / 'cron/.jobs.lock'), \
            r.writer_module().held_lock(state / 'writer.lock'):
        observations(request)
        no_uncertain_work(state)
        original_owner = l.private_bytes(state / 'controller/ownership.json')
        original_arming = l.private_json(state / 'controller/arming.json')
        protected_names = ['controller/arming.json', 'cron/jobs.json', 'auth.json', '.secrets.json']
        protected_names += [str(p.relative_to(state)) for p in sorted((state / 'controller').glob('acceptance-*.json'))]
        protected = {n: digest(l.private_bytes(state / n)) for n in protected_names}
        runs = state / 'controller/engineering-runs'
        retained = Path(tempfile.mkdtemp(prefix='packaging-adoption-', dir=runs))
        r.p.stage.atomic(retained / 'ownership-before.json', original_owner)
        r.p.stage.atomic(retained / 'authorization.json', r.p.stage.encoded(request))
        began = time.time()
        contained = False
        try:
            # Existing production stop revokes before systemd stop. No NAS action.
            contained = True
            r.stop(old)
            l.require(l.stopped(l.unit_state()), 'actual native process must stop')
            with r.writer_module().held_lock(state / 'controller/runtime.lock'):
                work = no_uncertain_work(state)
                data, checkpoint = r.p.checkpoint(state, (*DATABASES, *protected_names), exclusive_owner=True)
                normalized, validations = r.p.normalized_databases(data, checkpoint)
                archive = retained / 'checkpoint'
                r.p.stage.mkdir(archive)
                for name, raw in data.items():
                    r.p.stage.atomic(archive / name, raw)
                r.p.stage.atomic(retained / 'checkpoint.json', r.p.stage.encoded(checkpoint))
                r.p.stage.atomic(retained / 'database-validations.json', r.p.stage.encoded(validations))
                activation_log = retained / 'activation.log'
                with activation_log.open('wb') as output:
                    result = subprocess.run([str(candidate / 'activate')], stdout=output, stderr=subprocess.STDOUT,
                                            timeout=240, cwd='/')
                l.require(result.returncode == 0, 'activation failed; retained targeted log; native remains revoked')
                installed_generation = (home / '.local/state/nix/profiles/home-manager').resolve(strict=True)
                l.require(installed_generation == candidate and metadata(installed_generation) == new,
                          'exact intended standalone installed generation required')
                l.require(l.stopped(l.unit_state()), 'activation must not start an owner')
                for name, sha in protected.items():
                    l.require(digest(l.private_bytes(state / name)) == sha, 'activation changed protected state')
                for name, raw in data.items():
                    l.require(r.p.stage.read_private(state / name, owner=os.getuid()) == raw,
                              'activation changed database/checkpoint bytes')
                no_uncertain_work(state)
                l.require(time.time() < request['freeze']['expiresAt'], 'approved window expired during activation')
                l.bound_unit(home, new, l.unit_state())
                evidence = {'schemaVersion': 1, 'kind': 'HERMES771_REVIEWED_ONE_TIME_PACKAGING_ADOPTION',
                            'namespace': l.NAMESPACE, 'authorization': request['authorization'],
                            'sourceBundleSha256': original_arming['sourceBundleSha256'],
                            'originalGeneration': str(original_generation), 'currentGeneration': str(candidate),
                            'originalAcceptedCode': original_arming['code'], 'previousCode': old_code,
                            'currentCode': new_code, 'futureAutomaticResume': False,
                            'protectedRecords': protected, 'noActiveOrUncertainWork': work,
                            'source': request['source'], 'peers': request['peers'],
                            'recordedAt': time.time(), 'retentionDaysMinimum': 14,
                            'acceptance': 'ORIGINAL_RECEIPTS_PRESERVED_NOT_REPEATED',
                            'distinctScheduledBrief': 'PENDING', 'approval': str(retained / 'authorization.json')}
                evidence_path = retained / 'qualification.json'
                evidence_raw = r.p.stage.encoded(evidence)
                r.p.stage.atomic(evidence_path, evidence_raw)
                owner_path = state / 'controller/ownership.json'
                before = r.p.signature(owner_path)
                owner = l.private_json(owner_path)
                l.require(owner.get('phase') == 'STOPPED_REVIEW_REQUIRED'
                          and all(owner.get(k) == 'DISABLED' for k in l.CAPABILITIES), 'exact revoked owner CAS required')
                owner.update(phase='NATIVE_LIVE', **{k: 'ENABLED' for k in l.CAPABILITIES},
                             packagingAdoptionEvidence=str(evidence_path),
                             packagingAdoptionEvidenceSha256=digest(evidence_raw),
                             packagingAdoptedAt=time.time(), observationStatus='PENDING')
                r.p.atomic_durable(owner_path, r.p.stage.encoded(owner), before)
            # Explicit reviewed one-time route. Ordinary start still requires its
            # original exact arming gate; this is not a restart retry/fallback.
            r.systemctl('daemon-reload')
            r.systemctl('start', l.SERVICE)
            deadline = time.monotonic() + 40
            ready = None
            while time.monotonic() < deadline:
                unit = l.unit_state()
                l.require(unit.get('ActiveState') not in {'failed', 'inactive'}, 'new supervisor exited; review required')
                invocation = r.systemctl('show', l.SERVICE, '-p', 'InvocationID', '--value').decode().strip()
                journal = subprocess.run(['/usr/bin/journalctl', '--user', '_SYSTEMD_INVOCATION_ID=' + invocation,
                                          '--no-pager', '-o', 'cat'], env=l.SYSTEMD_ENV, capture_output=True, check=True).stdout
                if b'Connected to Telegram (polling mode)' in journal:
                    l.require(l.preflight(home, candidate) == 'UNCHANGED_LIVE_IDENTITY', 'new exact owner/unit binding required')
                    ready = {'invocationID': invocation, 'mainPID': int(unit['MainPID']),
                             'actualTelegramPollingConnection': True, 'verifiedAt': time.time(),
                             'maintenanceSeconds': time.time() - began,
                             'continuousAvailability': 'NOT_CLAIMED', 'scheduledDelivery': 'PENDING'}
                    break
                time.sleep(1)
            l.require(ready is not None, 'actual new Telegram poller connection not observed; contain for review')
            for name, sha in protected.items():
                if name != 'auth.json':
                    l.require(digest(l.private_bytes(state / name)) == sha, 'protected receipt/secret/job changed during restart')
            # Fresh native provider refresh may legitimately advance auth.json.
            # Never restore its preimage; retain latest post-start bytes instead.
            ready['latestAuthSha256'] = digest(l.private_bytes(state / 'auth.json'))
            r.p.stage.atomic(retained / 'readiness.json', r.p.stage.encoded(ready))
            return {'adoption': 'INSTALLED_READY_CONNECTION_OBSERVED', 'evidence': str(evidence_path), **ready}
        except BaseException:
            if contained:
                try:
                    r.stop(old)
                except BaseException:
                    pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    parser.add_argument('--candidate-generation', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--qualify', action='store_true')
    group.add_argument('--adopt', action='store_true')
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    candidate = args.candidate_generation.resolve(strict=True)
    l.require(candidate.is_relative_to(l.STORE) and candidate.name.endswith('-home-manager-generation'),
              'actual immutable standalone candidate generation required')
    if args.qualify:
        original, old, new, old_code, new_code = qualify(args.home, candidate)
        print(json.dumps({'qualification': 'EXACT_REVIEWED_PACKAGING_ONLY',
                          'originalGeneration': str(original), 'candidateGeneration': str(candidate)}))
    else:
        l.require(args.request is not None, 'explicit private John window/observations required')
        print(json.dumps(adopt(args.home, candidate, l.private_json(args.request)), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('Hermes packaging adoption FAILED/REFUSED; preserve retained evidence and review; '
              'no automatic retry/rollback/NAS resume. ' + str(error), file=sys.stderr)
        sys.exit(1)
