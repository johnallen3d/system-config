#!/usr/bin/env python3
"""One native mirror owner. Never overwrite drift or resume a job in staging."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

import yaml

PRIORITY = ['food', 'food-label', 'activity', 'weight', 'macros', 'macros-details',
            'recipe', 'task', 'video', 'search']
DISPLAY = dict(notifications='important', interim_assistant_messages=False,
               thinking_progress=False, tool_progress='all',
               tool_progress_grouping='accumulate', cleanup_progress=True,
               long_running_notifications=False)
EXCEPTIONS = ['execute_code', 'script execution via heredoc', 'shell command via -c/-lc flag']


def safe(path: Path, *, directory=False, missing=False):
    # Check every component, including in-root links pointing to another owned file.
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ValueError('symlink refused')
    if not path.exists():
        if missing:
            return
        raise ValueError('required path missing')
    info = path.stat()
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError('directory required')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('single-link regular file required')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data, mode=0o600):
    safe(path.parent, directory=True)
    safe(path, missing=True)
    if path.exists() and path.read_bytes() == data and stat.S_IMODE(path.stat().st_mode) == mode:
        return
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def reconcile(state: Path, assets: Path):
    safe(state, directory=True)
    safe(assets, directory=True)
    if os.environ.get('HERMES_NATIVE_STAGE') != 'capabilities-offline':
        raise ValueError('offline staging gate required')
    # #760 permits ONLY receipt-verified restricted state. Reconciliation still
    # cannot import credentials, resume queues or rotate the production grant.
    auth = state / 'auth.json'
    safe(auth, missing=True)
    if auth.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location('state_stage', assets / 'state-stage.py')
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        receipt = state / 'state-staging.json'
        safe(receipt)
        stage.verify_receipt(json.loads(receipt.read_text()),
                             {'paths': {'state': str(state), 'home': os.environ['HOME']}})
    for name in ['pending', 'pending_messages']:
        path = state / name
        safe(path, directory=True, missing=True)
        if path.exists() and any(path.iterdir()):
            raise ValueError('queued work must remain quarantined')
    safe(state / '.env')
    if (state / '.env').read_bytes():
        raise ValueError('staging .env must be empty')
    safe(state / 'config.yaml')
    config = yaml.safe_load((state / 'config.yaml').read_text())
    if not isinstance(config, dict) or config.get('_config_version') != 44:
        raise ValueError('fresh config-44 namespace required')
    ledger_path = state / 'managed-assets.json'
    safe(ledger_path, missing=True)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    if not isinstance(ledger, dict):
        raise ValueError('invalid mirror ledger')
    provenance = json.loads((assets / 'provenance.json').read_text())
    desired = {}
    plans = []
    for record in provenance['assets']:
        if record['adoption'] == 'blocked-policy-drift':
            continue
        relative = record['path']
        source = assets / relative
        target = state / relative
        safe(source)
        safe(target, missing=True)
        data = source.read_bytes()
        current = digest(target.read_bytes()) if target.exists() else None
        new_hash = digest(data)
        if current is not None and current not in {new_hash, ledger.get(relative)}:
            raise ValueError('managed mirror drift preserved; review required: ' + relative)
        desired[relative] = new_hash
        plans.append((target, data, 0o700 if relative.endswith('adjust-food-log') else 0o600))
    # Only one morning-brief record, inactive forever at this gate. No scheduler API.
    jobs_path = state / 'cron/jobs.json'
    safe(jobs_path, missing=True)
    jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else {'jobs': []}
    if not isinstance(jobs, dict) or not isinstance(jobs.get('jobs'), list):
        raise ValueError('invalid jobs file')
    matches = [j for j in jobs['jobs'] if j.get('name') == 'pi-cielo-morning-brief']
    if len(matches) > 1 or any(j.get('enabled', True) for j in jobs['jobs']):
        raise ValueError('duplicate or active jobs refused; no imported schedules')
    job = dict(id='native-staging-morning-brief', name='pi-cielo-morning-brief',
               schedule={'kind': 'cron', 'expr': '0 5 * * *'},
               script='morning-brief.sh', no_agent=True, prompt='', enabled=False,
               state='paused', paused_at='1970-01-01T00:00:00+00:00',
               paused_reason='Native staging; cutover not authorized.',
               created_at='1970-01-01T00:00:00+00:00', repeat={'times': None, 'completed': 0}, next_run_at=None,
               deliver=None, failure_deliver=None,
               workdir=str(state / 'workspace/notes'))
    if matches:
        jobs['jobs'][jobs['jobs'].index(matches[0])] = job
    else:
        jobs['jobs'].append(job)
    # Preserve unrelated preference keys; enforce the managed offline boundary.
    config.update(terminal={'backend': 'local', 'cwd': str(state / 'workspace')},
                  platform_toolsets={'cli': [], 'telegram': []}, mcp_servers={},
                  plugins={'enabled': ['search', 'macros']}, command_allowlist=EXCEPTIONS)
    telegram = config.setdefault('platforms', {}).setdefault('telegram', {})
    telegram['enabled'] = False
    extra = telegram.setdefault('extra', {})
    menu = extra.setdefault('command_menu', {})
    existing_priority = menu.get('priority', [])
    if not isinstance(existing_priority, list) or not all(isinstance(item, str) for item in existing_priority):
        raise ValueError('invalid command-menu priority')
    menu['priority'] = PRIORITY + [item for item in existing_priority if item not in PRIORITY]
    menu['priority_mode'] = 'prepend'
    config.setdefault('display', {}).setdefault('platforms', {})['telegram'] = DISPLAY
    config.setdefault('security', {})['redact_secrets'] = True
    safe(assets / 'morning-brief.sh')
    script = (assets / 'morning-brief.sh').read_bytes()
    script_path = state / 'scripts/morning-brief.sh'
    safe(script_path, missing=True)
    previous = ledger.get('scripts/morning-brief.sh')
    if script_path.exists() and digest(script_path.read_bytes()) not in {digest(script), previous}:
        raise ValueError('morning brief mirror drift preserved')
    # Preflight all destination parents before writing any owned mirror.
    for path in [state / 'scripts', state / 'cron', *[target.parent for target, _, _ in plans]]:
        safe(path, directory=True, missing=True)
    for target, data, mode in plans:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic(target, data, mode)
    for path in [state / 'scripts', state / 'cron']:
        path.mkdir(exist_ok=True, mode=0o700)
    atomic(script_path, script, 0o700)
    desired['scripts/morning-brief.sh'] = digest(script)
    atomic(jobs_path, encoded(jobs))
    atomic(state / 'config.yaml', encoded(config))
    atomic(ledger_path, encoded(desired))
    # Intentionally does not imply task parity, imported-state health or production readiness.
    return {'owner': 'system-config', 'mirrors': len(desired), 'morning_brief': 'INACTIVE',
            'food_skill': 'LIVE_POLICY_STAGED', 'custom_skills': 'PRIVATE_USER_STATE_GATES_PENDING',
            'messages': 'UNSUPPORTED_SCHEMA', 'production_ready': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, type=Path)
    parser.add_argument('--assets', required=True, type=Path)
    args = parser.parse_args()
    try:
        safe(args.state, directory=True)
        lock = args.state / '.managed-assets.lock'
        safe(lock, missing=True)
        with lock.open('a+') as stream:
            os.chmod(lock, 0o600)
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            print(json.dumps(reconcile(args.state, args.assets), sort_keys=True))
    except (ValueError, OSError, KeyError, json.JSONDecodeError, yaml.YAMLError):
        raise SystemExit('Native reconciliation refused; private drift/state is preserved. Review the staging inputs.')


if __name__ == '__main__':
    main()
