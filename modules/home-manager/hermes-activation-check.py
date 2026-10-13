#!/usr/bin/env python3
"""Read-only #771 Home Manager preflight. Never stop/start/rebind an owner.

A candidate that changes a native-owned running service must fail before
writeBoundary. An explicitly revoked, stopped owner may install new code, but
this does not authorize arming, receipt replacement, replay or service start.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

NAMESPACE = 'production/baseline-0.21.2'
SERVICE = 'hermes-production.service'
STORE = Path('/nix/store')
CAPABILITIES = ('poller', 'scheduler', 'vaultWrites', 'providerRefresh')
ACCEPTANCE_RECEIPTS = ('acceptance-probe.json', 'acceptance-inbound.json',
                      'acceptance-canary.json', 'acceptance-brief.json',
                      'acceptance-noeffect-continuation.json',
                      'acceptance-final-gate-continuation.json', 'initial-acceptance.json')
# One reviewed initial packaging patch, not a general code-change exception.
OLD_MODULE_SHA = '00de3ac2a16f3c8f6422c9efee229c4dae679eff1a2a75b1d565656fd4381f93'
NEW_MODULE_SHA = '832fa5e1d15ca7a1cfefb172cf5667e36e14cf234d725fd90741cb6102b8f574'
OLD_SOURCE_RUNTIME_SHA = 'acfcb5ff27a2c6e44485993de9133ec45d8e22fa5ec039881ca29cdd4105448b'
NEW_SOURCE_RUNTIME_SHA = '9d2ac9a6fb154907508992845c75bcd48b683822178319b1b5b31082ff59206b'
SOURCE_AUTHORIZATION = 'JOHN_FINISH_781_CONTROLLED_NATIVE_UPDATE'
SOURCE_USER_APPROVAL = 'JOHN_AUTHORIZED_FINISHING_781_AFTER_NATIVE_STOP_UPDATE_RESUME_PROPOSAL'
SYSTEMD_ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C',
               'XDG_RUNTIME_DIR': f'/run/user/{os.getuid()}',
               'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{os.getuid()}/bus'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def private_bytes(path):
    """No symlinks/foreign owner; bound reads; detect replacement during read."""
    for part in [*reversed(path.parents), path]:
        require(not part.is_symlink(), 'controller symlink refused')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid == os.getuid() and before.st_size <= 4 * 1024 * 1024,
                'private controller record required')
        data = stream.read(4 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(signature(before) == signature(after) == signature(path.stat()),
            'controller moved during read')
    return data


def private_json(path):
    value = json.loads(private_bytes(path))
    require(isinstance(value, dict), 'controller object required')
    return value


def immutable_json(path):
    target = path.resolve(strict=True)
    require(target.is_relative_to(STORE), 'immutable Home Manager metadata required')
    value = json.loads(target.read_bytes())
    require(isinstance(value, dict) and value.get('namespace') == NAMESPACE
            and value.get('service') == SERVICE, 'fixed production metadata required')
    return value


def identity(metadata):
    assets = Path(metadata['managedAssets'])
    require(assets.is_relative_to(STORE) and assets.is_dir(), 'immutable assets required')
    digest = lambda b: hashlib.sha256(b).hexdigest()
    result = {p.relative_to(assets).as_posix(): digest(p.read_bytes())
              for p in sorted(assets.rglob('*')) if p.is_file()}
    # Exactly production-runtime.engineering_identity; do not strip store hashes.
    result['@metadata'] = digest((json.dumps(metadata, sort_keys=True, indent=2) + '\n').encode())
    return result


def unit_state():
    output = subprocess.run(
        ['/usr/bin/systemctl', '--user', 'show', SERVICE,
         '-p', 'LoadState', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID',
         '-p', 'FragmentPath', '-p', 'ExecStart', '-p', 'Restart', '-p', 'DropInPaths'],
        env=SYSTEMD_ENV, capture_output=True, check=True, timeout=15).stdout.decode()
    return dict(line.split('=', 1) for line in output.splitlines() if '=' in line)


def stopped(unit):
    return unit.get('ActiveState') in {'inactive', 'failed'} and unit.get('MainPID') == '0'


def reviewed_task_binding(state, owner, arming, metadata, code):
    """Recognize retained #774 approval, never approve another code change/start.

    The arming-hashed calendar review binds current arming and the original
    acceptance receipts. The owner-hashed task review binds the exact installed
    identity to its immutable generation. Historical packaging evidence is not
    a substitute for either binding, and invalid newer evidence fails closed.
    """
    calendar_path = Path(arming.get('currentNativeCalendarReview', '/nonexistent'))
    require(owner.get('phase') == 'NATIVE_LIVE'
            and owner.get('currentNativeCalendarReview') == str(calendar_path)
            and calendar_path.parent.parent == state / 'controller/calendar-deployments'
            and calendar_path.parent.name.startswith('review-')
            and calendar_path.name == 'review.json', 'fixed retained calendar review required')
    raw = private_bytes(calendar_path)
    require(hashlib.sha256(raw).hexdigest() == arming.get('currentNativeCalendarReviewSha256'),
            'retained calendar review digest mismatch')
    calendar = json.loads(raw)
    require(isinstance(calendar, dict), 'retained calendar review object required')
    generation = Path(calendar.get('generation', '/nonexistent'))
    require(calendar.get('kind') == 'HERMES763_REVIEWED_CURRENT_NATIVE_CALENDAR_CODE_CONTINUATION'
            and calendar.get('namespace') == NAMESPACE
            and calendar.get('authorization') == 'JOHN_CALENDAR_ONLY_CONTROLLED_DEPLOYMENT_2026_10_11'
            and calendar.get('sourceBundleSha256') == owner['sourceBundleSha256']
            and calendar.get('code') == arming['code']
            and calendar.get('initialAcceptance') == 'PRESERVED_NOT_RERUN'
            and generation.is_relative_to(STORE) and generation.is_dir()
            and identity(immutable_json(generation / 'home-files/.config/hermes-native/production.json'))
                == arming['code'], 'retained calendar review does not bind current arming')
    acceptance = calendar.get('preservedAcceptance', {})
    require(isinstance(acceptance, dict), 'retained acceptance hashes required')
    for name in ACCEPTANCE_RECEIPTS:
        require(hashlib.sha256(private_bytes(state / 'controller' / name)).hexdigest()
                == acceptance.get(name), 'original acceptance receipt changed')

    path = Path(owner['currentNativeTaskAccessReview'])
    require(path.parent.parent == state / 'controller/task-access-deployments'
            and path.parent.name.startswith('review-774-')
            and path.name == 'qualification.json', 'fixed retained task-access review required')
    raw = private_bytes(path)
    require(hashlib.sha256(raw).hexdigest() == owner.get('currentNativeTaskAccessReviewSha256'),
            'retained task-access review digest mismatch')
    review = json.loads(raw)
    require(isinstance(review, dict), 'retained task-access review object required')
    generation = Path(review.get('generation', '/nonexistent'))
    require(review.get('schemaVersion') == 1
            and review.get('kind') == 'HERMES774_AUTHORIZED_SAME_NATIVE_OWNER_TASK_ACCESS_DEPLOYMENT'
            and review.get('namespace') == NAMESPACE and review.get('card') == 774
            and review.get('authorization') == 'JOHN_GO_AHEAD_AND_DEPLOY'
            and review.get('futureAutomaticResume') is False
            and review.get('historicalArmingAndAcceptance') == 'UNCHANGED'
            and review.get('canonicalStateAndCredentials') == 'COLD_PRESERVED_NO_REIMPORT_OR_REPLAY'
            and review.get('code') == code
            and generation.is_relative_to(STORE) and generation.is_dir()
            and immutable_json(generation / 'home-files/.config/hermes-native/production.json') == metadata,
            'retained task-access review does not approve this exact installed identity')


def source_path_diff(previous, current):
    changed = {k for k in set(previous) | set(current) if previous.get(k) != current.get(k)}
    require(set(previous) == set(current) and changed == {'@metadata', 'production-runtime.py'}
            and previous.get('production-runtime.py') == OLD_SOURCE_RUNTIME_SHA
            and current.get('production-runtime.py') == NEW_SOURCE_RUNTIME_SHA,
            'only exact reviewed #781 source-path runtime change permitted')


def reviewed_source_path_binding(state, owner, arming, metadata, code):
    """Retained one-off #781 binding; never approve another candidate or restart."""
    path = Path(owner['currentSourcePathReview'])
    require(owner.get('phase') == 'NATIVE_LIVE'
            and path.parent.parent == state / 'controller/source-path-deployments'
            and path.parent.name.startswith('review-781-') and path.name == 'qualification.json',
            'fixed retained source-path review required')
    raw = private_bytes(path)
    require(hashlib.sha256(raw).hexdigest() == owner.get('currentSourcePathReviewSha256'),
            'retained source-path review digest mismatch')
    review = json.loads(raw)
    require(isinstance(review, dict)
            and review.get('schemaVersion') == 1
            and review.get('kind') == 'HERMES781_AUTHORIZED_SAME_NATIVE_OWNER_SOURCE_PATH_DEPLOYMENT'
            and review.get('namespace') == NAMESPACE and review.get('card') == 781
            and review.get('authorization') == SOURCE_AUTHORIZATION
            and review.get('userApproval') == SOURCE_USER_APPROVAL
            and review.get('scope') == 'SOURCE_PATHS_ONLY_NO_VAULT_WRITES'
            and review.get('futureAutomaticResume') is False
            and review.get('historicalArmingAndAcceptance') == 'UNCHANGED'
            and review.get('canonicalStateAndCredentials') == 'COLD_PRESERVED_NO_REIMPORT_OR_REPLAY'
            and review.get('sourceBundleSha256') == owner['sourceBundleSha256']
            and review.get('code') == code,
            'retained source-path review does not approve this exact installed identity')
    approval_path = path.with_name('authorization.json')
    approval_raw = private_bytes(approval_path)
    approval = json.loads(approval_raw)
    require(hashlib.sha256(approval_raw).hexdigest() == review.get('approvalSha256')
            and isinstance(approval, dict)
            and approval.get('authorization') == SOURCE_AUTHORIZATION
            and approval.get('userApproval') == SOURCE_USER_APPROVAL
            and approval.get('approvedAction') == 'NATIVE_ONLY_STOP_UPDATE_SAME_OWNER_RESUME'
            and approval.get('authorizationBasis') == 'DIRECT_USER_INSTRUCTION_IN_RESPONSE_TO_PROPOSAL'
            and isinstance(approval.get('userRequest'), str) and bool(approval['userRequest'].strip()),
            'retained explicit source-path authorization mismatch')
    previous_generation = Path(review.get('previousGeneration', '/nonexistent'))
    generation = Path(review.get('generation', '/nonexistent'))
    require(previous_generation.is_relative_to(STORE) and previous_generation.is_dir()
            and generation.is_relative_to(STORE) and generation.is_dir(),
            'immutable source-path generations required')
    previous = immutable_json(previous_generation / 'home-files/.config/hermes-native/production.json')
    previous_code = identity(previous)
    require(review.get('previousCode') == previous_code
            and immutable_json(generation / 'home-files/.config/hermes-native/production.json') == metadata,
            'source-path immutable generation binding mismatch')
    source_path_diff(previous_code, code)
    # The previous deployment must still have the complete original approval chain.
    reviewed_task_binding(state, owner, arming, previous, previous_code)
    protected = review.get('protectedRecords', {})
    for name in ('arming.json', *ACCEPTANCE_RECEIPTS):
        require(hashlib.sha256(private_bytes(state / 'controller' / name)).hexdigest()
                == protected.get('controller/' + name), 'source-path historical receipt changed')


def authority(home, metadata, unit):
    state = Path(metadata['paths']['state'])
    require(state == home / '.local/state/hermes-native/production/baseline-0.21.2',
            'fixed production controller path required')
    path = state / 'controller/ownership.json'
    if not path.exists() and not path.is_symlink():
        require(stopped(unit), 'missing owner with running/transitioning service')
        return None
    owner = private_json(path)
    require(owner.get('schemaVersion') == 1 and owner.get('namespace') == NAMESPACE,
            'unknown ownership record')
    if owner.get('owner') == 'nas' and owner.get('phase') == 'CLOSED':
        require(stopped(unit) and all(owner.get(k) == 'DISABLED' for k in CAPABILITIES),
                'NAS/CLOSED must have no native authority or process')
        return owner
    require(owner.get('owner') == 'native', 'unknown owner; review required')
    if owner.get('phase') == 'STOPPED_REVIEW_REQUIRED':
        require(stopped(unit) and all(owner.get(k) == 'DISABLED' for k in CAPABILITIES),
                'revoked owner must be fully stopped before activation')
        return owner
    require(owner.get('phase') in {'NATIVE_ARMED', 'NATIVE_LIVE'}
            and unit.get('ActiveState') == 'active' and unit.get('SubState') == 'running'
            and int(unit.get('MainPID', '0')) > 0, 'native owner/service disagreement; review required')
    require(owner.get('poller') == 'ENABLED', 'running owner without poller authority')
    arming = private_json(state / 'controller/arming.json')
    require(arming.get('namespace') == NAMESPACE and arming.get('status') == 'ARMED'
            and isinstance(owner.get('sourceBundleSha256'), str) and bool(owner['sourceBundleSha256'])
            and arming.get('sourceBundleSha256') == owner.get('sourceBundleSha256'),
            'installed arming/owner binding mismatch')
    code = identity(metadata)
    if arming.get('code') != code and owner.get('currentSourcePathReview'):
        reviewed_source_path_binding(state, owner, arming, metadata, code)
    elif arming.get('code') != code and owner.get('currentNativeTaskAccessReview'):
        reviewed_task_binding(state, owner, arming, metadata, code)
    elif arming.get('code') != code and owner.get('packagingAdoptionEvidence'):
        evidence_path = Path(owner['packagingAdoptionEvidence'])
        require(evidence_path.parent.parent == state / 'controller/engineering-runs'
                and evidence_path.parent.name.startswith('packaging-adoption-')
                and evidence_path.name == 'qualification.json', 'fixed packaging approval path required')
        raw = private_bytes(evidence_path)
        require(hashlib.sha256(raw).hexdigest() == owner.get('packagingAdoptionEvidenceSha256'),
                'packaging approval digest mismatch')
        evidence = json.loads(raw)
        generation = Path(evidence.get('currentGeneration', '/nonexistent'))
        excluded = {'@metadata', 'production-module.nix'}
        require(evidence.get('kind') == 'HERMES771_REVIEWED_ONE_TIME_PACKAGING_ADOPTION'
                and evidence.get('authorization') == 'JOHN_APPROVED_771_CONTROLLED_PACKAGING_ADOPTION'
                and evidence.get('namespace') == NAMESPACE
                and evidence.get('sourceBundleSha256') == owner['sourceBundleSha256']
                and evidence.get('futureAutomaticResume') is False
                and evidence.get('originalAcceptedCode') == arming['code']
                and evidence.get('currentCode') == code
                and arming['code'].get('production-module.nix') == OLD_MODULE_SHA
                and code.get('production-module.nix') == NEW_MODULE_SHA
                and {k: v for k, v in arming['code'].items() if k not in excluded}
                    == {k: v for k, v in code.items() if k not in excluded}
                and generation.is_relative_to(STORE) and generation.is_dir()
                and immutable_json(generation / 'home-files/.config/hermes-native/production.json') == metadata,
                'packaging receipt does not approve this exact installed identity')
    elif arming.get('code') != code:
        # The audited one-off recovery preserved the original arming receipt.
        # Recognize ONLY its exact current binding; never normalize a new candidate
        # or manufacture/refresh receipts, and never authorize another resume.
        evidence_path = Path(owner.get('resumptionEvidence', '/nonexistent'))
        runs = state / 'controller/engineering-runs'
        require(owner.get('phase') == 'NATIVE_LIVE' and evidence_path.parent.parent == runs
                and evidence_path.parent.name.startswith('authorized-same-owner-resumption-')
                and evidence_path.name == 'qualification.json', 'installed code/arming binding mismatch')
        raw = private_bytes(evidence_path)
        require(hashlib.sha256(raw).hexdigest() == owner.get('resumptionEvidenceSha256'),
                'retained resumption evidence digest mismatch')
        evidence = json.loads(raw)
        generation = Path(evidence.get('currentGeneration', '/nonexistent'))
        require(evidence.get('kind') == 'HERMES763_AUTHORIZED_SAME_ACCEPTED_OWNER_METADATA_ONLY_RESUMPTION'
                and evidence.get('namespace') == NAMESPACE
                and evidence.get('authorization') == 'JOHN_NATIVE_REPAIR_AND_RESTART_ONLY'
                and evidence.get('futureAutomaticResume') is False
                and evidence.get('originalArmingAndAcceptance') == 'UNCHANGED'
                and evidence.get('allAssetAndFixtureBytes') == 'IDENTICAL'
                and evidence.get('acceptedCode') == arming['code']
                and evidence.get('currentCode') == code
                and {k: v for k, v in arming['code'].items() if k != '@metadata'}
                    == {k: v for k, v in code.items() if k != '@metadata'}
                and generation.is_relative_to(STORE) and generation.is_dir()
                and immutable_json(generation / 'home-files/.config/hermes-native/production.json') == metadata,
                'retained resumption does not approve this installed identity')
    return owner


def bound_unit(home, metadata, unit):
    installed_unit = home / '.config/systemd/user' / SERVICE
    require(installed_unit.resolve(strict=True).is_relative_to(STORE)
            and unit.get('FragmentPath') == str(installed_unit) and unit.get('Restart') == 'no'
            and unit.get('ExecStart', '').startswith('{ path=' + metadata['launcher'] + ' ;'),
            'effective unit differs from bound foreground supervisor')
    dropin = Path(SYSTEMD_ENV['XDG_RUNTIME_DIR']) / 'systemd/user' / (SERVICE + '.d/763-cutover.conf')
    require(unit.get('DropInPaths') == str(dropin)
            and not dropin.is_symlink()
            and dropin.read_bytes() == b'[Unit]\nRefuseManualStart=false\n',
            'unexpected effective unit override')


def preflight(home, generation):
    candidate = immutable_json(generation / 'home-files/.config/hermes-native/production.json')
    unit = unit_state()
    installed_path = home / '.config/hermes-native/production.json'
    if not installed_path.exists() and not installed_path.is_symlink():
        owner = authority(home, candidate, unit)
        require(owner is None or owner.get('phase') in {'CLOSED', 'STOPPED_REVIEW_REQUIRED'},
                'installed metadata missing for native owner')
        return 'STOPPED_INSTALL_ONLY'
    installed = immutable_json(installed_path)
    owner = authority(home, installed, unit)
    if owner is None or owner.get('phase') in {'CLOSED', 'STOPPED_REVIEW_REQUIRED'}:
        return 'STOPPED_INSTALL_ONLY'
    require(candidate == installed,
            'candidate changes native ownership identity; controlled stop/review required')
    installed_unit = home / '.config/systemd/user' / SERVICE
    candidate_unit = generation / 'home-files/.config/systemd/user' / SERVICE
    require(installed_unit.resolve(strict=True).is_relative_to(STORE)
            and candidate_unit.resolve(strict=True).is_relative_to(STORE)
            and installed_unit.read_bytes() == candidate_unit.read_bytes(),
            'candidate changes installed unit; controlled stop/review required')
    bound_unit(home, installed, unit)
    return 'UNCHANGED_LIVE_IDENTITY'


def status(home):
    """Configured jobs are not evidence of scheduler execution or delivery."""
    metadata = immutable_json(home / '.config/hermes-native/production.json')
    unit = unit_state()
    owner = authority(home, metadata, unit)
    if owner and owner.get('phase') in {'NATIVE_ARMED', 'NATIVE_LIVE'}:
        bound_unit(home, metadata, unit)
    enabled = bool(owner and owner.get('phase') == 'NATIVE_LIVE'
                   and owner.get('scheduler') == 'ENABLED' and not stopped(unit))
    jobs = private_json(Path(metadata['paths']['state']) / 'cron/jobs.json')
    return {'ownershipPhase': owner.get('phase') if owner else 'MISSING',
            'serviceActiveState': unit.get('ActiveState'), 'schedulerAuthorized': enabled,
            'telegramReadiness': 'NOT_PROBED', 'scheduledDelivery': 'NOT_VERIFIED',
            'jobs': [{'id': job.get('id'), 'configuredEnabled': bool(job.get('enabled')),
                      'executionAuthorized': enabled and owner.get('vaultWrites') == 'ENABLED'
                          and bool(job.get('enabled'))}
                     for job in jobs.get('jobs', [])]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--candidate-generation', type=Path)
    group.add_argument('--status', action='store_true')
    args = parser.parse_args()
    require(args.home.is_absolute(), 'absolute home required')
    result = status(args.home) if args.status else {'activation': preflight(args.home, args.candidate_generation)}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f'Hermes lifecycle check REFUSED: {error}. '
              'Do not bypass receipts, restart, or restore NAS state; see docs/hermes-activation-lifecycle.md.',
              file=sys.stderr)
        sys.exit(1)
