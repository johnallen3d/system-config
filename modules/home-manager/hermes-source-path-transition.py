#!/usr/bin/env python3
"""#781 one-time, exact source-path update of the already accepted native owner.

No vault writes/restores, receipt rebinding, acceptance replay, NAS actions or
future automatic resumption. --qualify is read-only. --deploy requires John's
scoped private authorization and fresh source observations over parent stdio;
that parent must use its existing trusted NAS SSH connection, never copy keys.
Only local native writer/scheduler locks are held; no distributed/human writer
freeze is claimed or manufactured for this code-only update.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


l = module('source_lifecycle', Path(__file__).with_name('hermes-activation-check.py'))
a = module('source_adoption_support', Path(__file__).with_name('hermes-packaging-adopt.py'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def equivalent(old, new, old_unit, new_unit):
    """Only exact immutable pointer translations; no hash or identity exemptions."""
    expected = copy.deepcopy(old)
    replacements = {}
    for key in a.POINTERS:
        replacements[old[key]] = new[key]
        expected[key] = new[key]
    for key in a.ENV_POINTERS:
        replacements[old['environment'][key]] = new['environment'][key]
        expected['environment'][key] = new['environment'][key]
    l.require(expected == new, 'metadata semantics changed outside source-path repair')
    # The operator is the single fixed pre/postimage checked by source_path_diff.
    for key in ('transferOperator', 'productionFixture', 'writerFixture'):
        l.require(Path(old[key]).read_bytes() == Path(new[key]).read_bytes(),
                  'unreviewed transfer/fixture change')
    sibling = 'hermes-native-production-state.py'
    l.require(Path(old['productionFixture']).with_name(sibling).read_bytes()
              == Path(new['productionFixture']).with_name(sibling).read_bytes(),
              'unreviewed state fixture change')
    translated = Path(old['launcher']).read_bytes()
    translated_unit = old_unit
    for before, after in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(before.encode(), after.encode())
        translated_unit = translated_unit.replace(before.encode(), after.encode())
    l.require(translated == Path(new['launcher']).read_bytes(), 'launcher semantics changed')
    l.require(translated_unit == new_unit, 'unit semantics changed')


def qualify(home, candidate, source):
    original = (home / '.local/state/nix/profiles/home-manager').resolve(strict=True)
    old, new = a.metadata(original), a.metadata(candidate)
    l.require(l.preflight(home, original) == 'UNCHANGED_LIVE_IDENTITY',
              'exact currently approved live owner required')
    state = Path(old['paths']['state'])
    owner = l.private_json(state / 'controller/ownership.json')
    l.require(owner.get('phase') == 'NATIVE_LIVE'
              and all(owner.get(k) == 'ENABLED' for k in l.CAPABILITIES)
              and not owner.get('currentSourcePathReview'), 'one-time source-path update only')
    previous, current = l.identity(old), l.identity(new)
    l.source_path_diff(previous, current)
    equivalent(old, new,
               (original / 'home-files/.config/systemd/user' / l.SERVICE).read_bytes(),
               (candidate / 'home-files/.config/systemd/user' / l.SERVICE).read_bytes())
    runtime = a.controller(new)
    source = runtime.engineering_source(new, str(source))
    for name, sha in current.items():
        if not name.startswith('@'):
            l.require(digest(l.private_bytes(source / 'modules/home-manager/hermes-native' / name)) == sha,
                      'exact candidate source asset CAS required')
    return original, old, new, previous, current


def authorization(request):
    now = time.time()
    l.require(request.get('authorization') == l.SOURCE_AUTHORIZATION
              and request.get('userApproval') == l.SOURCE_USER_APPROVAL
              and request.get('approvedAction') == 'NATIVE_ONLY_STOP_UPDATE_SAME_OWNER_RESUME'
              and request.get('authorizationBasis') == 'DIRECT_USER_INSTRUCTION_IN_RESPONSE_TO_PROPOSAL'
              and isinstance(request.get('userRequest'), str) and bool(request['userRequest'].strip())
              and request.get('requestedAt', 0) <= now < request.get('expiresAt', 0)
              and 0 < request['expiresAt'] - request['requestedAt'] <= 600,
              'fresh explicit bounded native-only authorization required')


def observation(proof, arming):
    now = time.time()
    original = arming['sourceProof']
    l.require(proof.get('running') is False and proof.get('pid') == 0
              and proof.get('restartPolicy') == 'no' and proof.get('managedRetirement') is True
              and 0 <= now - proof.get('observedAt', 0) <= 30
              and all(proof.get(key) == original.get(key) for key in
                      ('containerID', 'imageID', 'revision', 'retirementSha256')),
              'fresh actual exact stopped/protected NAS observation required')


def stdio_source_observer():
    # No listener, shell, credentials or arbitrarily supplied remote command.
    print('SOURCE_OBSERVATION_REQUIRED', flush=True)
    line = sys.stdin.readline(65537)
    l.require(line.endswith('\n') and len(line) <= 65536, 'bounded fresh parent source observation required')
    value = json.loads(line)
    l.require(isinstance(value, dict), 'actual source observation object required')
    return value


def deploy(home, candidate, source, request, observe):
    os.umask(0o077)
    authorization(request)
    original, old, new, previous, current = qualify(home, candidate, source)
    state = Path(old['paths']['state'])
    r = a.controller(old)
    staging = r.systemctl('show', 'hermes-native.service', '-p', 'ActiveState', '-p', 'MainPID')
    l.require(b'ActiveState=inactive' in staging and b'MainPID=0' in staging, 'staging must remain inactive')
    a.no_uncertain_work(state)
    arming = l.private_json(state / 'controller/arming.json')
    initial_source = observe()
    observation(initial_source, arming)
    with r.scheduler_transition(old), r.writer_module().held_lock(state / 'cron/.jobs.lock'), \
            r.writer_module().held_lock(state / 'writer.lock'):
        authorization(request)
        observation(initial_source, arming)
        a.no_uncertain_work(state)
        owner_before = l.private_bytes(state / 'controller/ownership.json')
        protected_names = ['controller/arming.json', 'cron/jobs.json', 'auth.json', '.secrets.json']
        protected_names += ['controller/' + name for name in l.ACCEPTANCE_RECEIPTS]
        protected = {name: digest(l.private_bytes(state / name)) for name in protected_names}
        parent = state / 'controller/source-path-deployments'
        r.p.stage.mkdir(parent)
        retained = Path(tempfile.mkdtemp(prefix='review-781-', dir=parent))
        r.p.stage.atomic(retained / 'ownership-before.json', owner_before)
        approval_raw = r.p.stage.encoded(request)
        r.p.stage.atomic(retained / 'authorization.json', approval_raw)
        began = time.time()
        contained = False
        try:
            contained = True
            r.stop(old)  # Existing revoke-before-stop protocol; never touch NAS.
            l.require(l.stopped(l.unit_state()), 'native process must actually stop')
            with r.writer_module().held_lock(state / 'controller/runtime.lock'):
                work = a.no_uncertain_work(state)
                data, checkpoint = r.p.checkpoint(state, (*a.DATABASES, *protected_names), exclusive_owner=True)
                _, validations = r.p.normalized_databases(data, checkpoint)
                archive = retained / 'checkpoint'
                r.p.stage.mkdir(archive)
                for name, raw in data.items():
                    r.p.stage.atomic(archive / name, raw)
                r.p.stage.atomic(retained / 'checkpoint.json', r.p.stage.encoded(checkpoint))
                r.p.stage.atomic(retained / 'database-validations.json', r.p.stage.encoded(validations))
                authorization(request)
                with (retained / 'activation.log').open('wb') as output:
                    result = subprocess.run([str(candidate / 'activate')], stdout=output,
                                            stderr=subprocess.STDOUT, timeout=240, cwd='/')
                l.require(result.returncode == 0, 'activation failed; retain private log and stopped owner')
                l.require((home / '.local/state/nix/profiles/home-manager').resolve(strict=True) == candidate
                          and a.metadata(candidate) == new, 'exact intended generation required')
                l.require(l.stopped(l.unit_state()), 'activation must not start an owner')
                for name, sha in protected.items():
                    l.require(digest(l.private_bytes(state / name)) == sha, 'protected record changed')
                for name, raw in data.items():
                    l.require(r.p.stage.read_private(state / name, owner=os.getuid()) == raw,
                              'activation changed cold database/state bytes')
                authorization(request)
                final_source = observe()
                observation(final_source, arming)
                a.no_uncertain_work(state)
                l.bound_unit(home, new, l.unit_state())
                evidence = {'schemaVersion': 1,
                    'kind': 'HERMES781_AUTHORIZED_SAME_NATIVE_OWNER_SOURCE_PATH_DEPLOYMENT',
                    'namespace': l.NAMESPACE, 'card': 781,
                    'authorization': request['authorization'], 'userApproval': request['userApproval'],
                    'scope': 'SOURCE_PATHS_ONLY_NO_VAULT_WRITES', 'approvalSha256': digest(approval_raw),
                    'sourceBundleSha256': arming['sourceBundleSha256'],
                    'previousGeneration': str(original), 'generation': str(candidate),
                    'previousCode': previous, 'code': current, 'sourceRoot': str(source),
                    'futureAutomaticResume': False, 'historicalArmingAndAcceptance': 'UNCHANGED',
                    'canonicalStateAndCredentials': 'COLD_PRESERVED_NO_REIMPORT_OR_REPLAY',
                    'protectedRecords': protected, 'noActiveOrUncertainWork': work,
                    'actualSourceProof': final_source, 'recordedAt': time.time(),
                    'retentionDaysMinimum': 14, 'vaultMutationOrRestore': 'NONE',
                    'distributedWriterFreeze': 'NOT_CLAIMED'}
                path = retained / 'qualification.json'
                raw = r.p.stage.encoded(evidence)
                r.p.stage.atomic(path, raw)
                owner_path = state / 'controller/ownership.json'
                before = r.p.signature(owner_path)
                owner = l.private_json(owner_path)
                l.require(owner.get('phase') == 'STOPPED_REVIEW_REQUIRED'
                          and all(owner.get(key) == 'DISABLED' for key in l.CAPABILITIES),
                          'exact revoked owner CAS required')
                owner.update(phase='NATIVE_LIVE', **{key: 'ENABLED' for key in l.CAPABILITIES},
                             currentSourcePathReview=str(path), currentSourcePathReviewSha256=digest(raw),
                             sourcePathDeployedAt=time.time())
                r.p.atomic_durable(owner_path, r.p.stage.encoded(owner), before)
            r.systemctl('daemon-reload')
            r.systemctl('start', l.SERVICE)  # One explicitly authorized same-owner start, never a retry.
            deadline = time.monotonic() + 45
            ready = None
            while time.monotonic() < deadline:
                authorization(request)
                unit = l.unit_state()
                l.require(unit.get('ActiveState') not in {'failed', 'inactive'}, 'new supervisor exited')
                invocation = r.systemctl('show', l.SERVICE, '-p', 'InvocationID', '--value').decode().strip()
                journal = subprocess.run(['/usr/bin/journalctl', '--user', '_SYSTEMD_INVOCATION_ID=' + invocation,
                                          '--no-pager', '-o', 'cat'], env=l.SYSTEMD_ENV,
                                         capture_output=True, check=True).stdout
                if b'Connected to Telegram (polling mode)' in journal:
                    l.require(l.preflight(home, candidate) == 'UNCHANGED_LIVE_IDENTITY',
                              'exact new live owner/unit binding required')
                    observation(observe(), arming)
                    ready = {'mainPID': int(unit['MainPID']), 'invocationID': invocation,
                             'actualTelegramPollingConnection': True, 'verifiedAt': time.time(),
                             'maintenanceSeconds': time.time() - began,
                             'continuousAvailability': 'NOT_CLAIMED', 'scheduledDelivery': 'NOT_TESTED'}
                    break
                time.sleep(1)
            l.require(ready is not None, 'actual Telegram polling connection not observed')
            for name, sha in protected.items():
                if name != 'auth.json':
                    l.require(digest(l.private_bytes(state / name)) == sha, 'historical receipt/secret/job changed')
            ready['latestAuthSha256'] = digest(l.private_bytes(state / 'auth.json'))
            r.p.stage.atomic(retained / 'readiness.json', r.p.stage.encoded(ready))
            return {'update': 'READY', 'qualification': str(path), **ready}
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
    parser.add_argument('--source', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--qualify', action='store_true')
    group.add_argument('--deploy', action='store_true')
    parser.add_argument('--request', type=Path)
    parser.add_argument('--source-observer-stdio', action='store_true')
    args = parser.parse_args()
    candidate = args.candidate_generation.resolve(strict=True)
    l.require(candidate.is_relative_to(l.STORE) and candidate.name.endswith('-home-manager-generation'),
              'actual immutable standalone candidate required')
    if args.qualify:
        qualify(args.home, candidate, args.source)
        print(json.dumps({'qualification': 'EXACT_SOURCE_PATHS_ONLY'}))
    else:
        l.require(args.request is not None and args.source_observer_stdio,
                  'explicit private authorization and actual trusted parent observations required')
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        for signum in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(signum, interrupted)
        print(json.dumps(deploy(args.home, candidate, args.source,
                                l.private_json(args.request), stdio_source_observer), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError):
        print('Source-path update refused/failed; retain evidence and review stopped ownership; no retry or rollback.',
              file=sys.stderr)
        raise SystemExit(64)
