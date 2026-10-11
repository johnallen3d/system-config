#!/usr/bin/env python3
"""Fixed offline disposable checks, NOT a claim of vault/provider parity."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ASSETS = Path(sys.argv[1])


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ASSETS / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(argv, *, env=None, ok=True):
    result = subprocess.run(argv, env=env, capture_output=True, timeout=30)
    if ok and result.returncode:
        raise AssertionError('offline child failed (details intentionally not returned): ' + str(result.returncode))
    return result


def snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


def main():
    # The launcher provides a mount AND network namespace. HOME separation alone
    # is not a production write boundary, and this gate never runs arbitrary code.
    assert os.environ.get('HERMES_NATIVE_OFFLINE') == '1'
    assert not Path('/home/johna/notes').exists()
    assert not Path('/Users').exists()
    assert not any(k.startswith(('PI_', 'CLAUDE_')) or k.endswith(('TOKEN', 'API_KEY')) for k in os.environ)
    with socket.socket() as probe:
        probe.settimeout(0.2)
        try:
            probe.connect(('192.0.2.1', 443))  # Reserved TEST-NET; namespace must refuse.
        except OSError:
            pass
        else:
            raise AssertionError('network isolation missing')
    for name, version in [('mise', '2026.9.7'), ('vlt', '0.11.0'), ('gog', '0.40.0'), ('jq', '1.8.2'), ('yq', '4.53.6')]:
        output = run([name, '--version']).stdout.decode()
        assert version in output
    print('PASS native pinned mise/vlt/gog/jq/Mike-Farah-yq version execution (credential functionality NOT tested)')
    run([os.environ['HERMES_NATIVE_TASK_PYTHON'], '-I', '-c',
         'import yaml,PIL,pillow_heif,reportlab,pypdf,playwright; assert yaml.__version__ == "6.0.2"'])
    assert '0.8.2' in run(['uvx', '--from', 'notebooklm-py[browser]==0.8.2', 'notebooklm', '--version']).stdout.decode()
    assert '0.19.4' in run(['defuddle', '--version']).stdout.decode()
    print('PASS fixed offline pinned NotebookLM CLI and exact task Python/image/PDF/browser imports; no auth or provider calls')
    assert Path(os.environ['TZDIR'], 'America/New_York').is_file()
    for utc, expected in [('2026-10-11 00:00:00 UTC', '2026-10-10 20:00 -0400'),
                          ('2026-01-11 00:00:00 UTC', '2026-01-10 19:00 -0500'),
                          ('2026-03-08 07:00:00 UTC', '2026-03-08 03:00 -0400'),
                          ('2026-11-01 06:00:00 UTC', '2026-11-01 01:00 -0500')]:
        assert run(['date', '-d', utc, '+%F %H:%M %z']).stdout.decode().strip() == expected
    print('PASS pinned libc/GNU date New York UTC-midnight and both DST boundaries in sealed namespace')
    state = Path(os.environ['HERMES_HOME'])
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    Path(os.environ['HOME']).mkdir(parents=True, mode=0o700, exist_ok=True)
    from hermes_cli.config import _HERMES_HOME_SUBDIRS
    for directory in [*_HERMES_HOME_SUBDIRS, 'workspace/notes', 'pending', 'pending_messages']:
        (state / directory).mkdir(parents=True, mode=0o700, exist_ok=True)
    (state / '.env').write_bytes(b'')
    (state / 'config.yaml').write_text(json.dumps({'_config_version': 44, 'fixture_preference': 'retained'}))
    custom = state / 'skills/user/example/SKILL.md'
    custom.parent.mkdir(parents=True)
    custom.write_text('Synthetic unowned skill; retained, not executed.\n')
    reconcile = load('native_reconcile', 'reconcile.py')
    receipt = reconcile.reconcile(state, ASSETS)
    before = snapshot(state)
    assert reconcile.reconcile(state, ASSETS) == receipt
    assert snapshot(state) == before
    assert custom.read_text().startswith('Synthetic')
    config = json.loads((state / 'config.yaml').read_text())
    assert config['fixture_preference'] == 'retained'
    assert config['plugins']['enabled'] == ['search', 'macros']
    assert config['command_allowlist'] == reconcile.EXCEPTIONS
    assert not config['platforms']['telegram']['enabled'] and not config['mcp_servers']
    assert config['platform_toolsets'] == {'cli': [], 'telegram': []}
    assert config['display']['platforms']['telegram'] == reconcile.DISPLAY
    assert config['platforms']['telegram']['extra']['command_menu']['priority'] == reconcile.PRIORITY
    assert (state / 'skills/health/food/SKILL.md').is_file()
    assert 'transparent best-effort estimate' in (state / 'skills/health/food/SKILL.md').read_text()
    jobs = json.loads((state / 'cron/jobs.json').read_text())['jobs']
    assert len(jobs) == 1 and jobs[0]['enabled'] is False
    assert jobs[0]['no_agent'] and not jobs[0]['prompt']
    assert jobs[0]['deliver'] is None and jobs[0]['failure_deliver'] is None
    from cron.jobs import get_due_jobs
    assert get_due_jobs() == []  # Only a synthetic, paused fixture registration.
    # Genuine installed Hermes plugin discovery; no gateway or agent instantiated.
    from hermes_cli.plugins import discover_plugins, get_plugin_commands, get_plugin_command_handler
    discover_plugins(force=True)
    commands = get_plugin_commands()
    assert {'search', 'macros'} <= commands.keys()
    assert callable(get_plugin_command_handler('search'))
    assert callable(get_plugin_command_handler('macros'))
    print('PASS namespace: no production vault/profiles/network; installed plugin discovery; repeat reconciliation byte/mtime idempotence; one INACTIVE no-agent job')
    from gateway.display_config import resolve_display_setting, resolve_tool_progress
    for key, value in reconcile.DISPLAY.items():
        assert resolve_display_setting(config, 'telegram', key) == value
    assert resolve_tool_progress(config, 'telegram') == ('all', True)
    from hermes_cli.commands_platforms import telegram_menu_commands, telegram_menu_max_commands
    from agent.skill_commands import resolve_skill_command_key
    assert telegram_menu_max_commands() == 60
    menu, hidden = telegram_menu_commands(max_commands=5)
    assert [name for name, _ in menu] == ['food', 'food_label', 'activity', 'weight', 'macros']
    assert hidden > 0
    assert resolve_skill_command_key('food_label') == '/food-label'
    assert resolve_skill_command_key('macros_details') == '/macros-details'
    full_menu, _ = telegram_menu_commands(max_commands=60)
    assert len(full_menu) <= 60 and len({name for name, _ in full_menu}) == len(full_menu)
    assert {'recipe', 'task', 'video', 'search'} <= {name for name, _ in full_menu}
    assert 'food' in {name for name, _ in full_menu}
    print('PASS actual installed low-noise display resolver, Telegram priority-before-cap menu, unique names and underscore skill aliases; live food policy staged (no bot/API or production writers invoked)')

    # Real pinned mise invocation against deliberately synthetic task adapters.
    # They prove argument/environment dispatch, NOT the external vault task bodies.
    vault = state / 'workspace/notes'
    task_dir = vault / '.mise/tasks'
    task_dir.mkdir(parents=True)
    scripts = {
        'common-food': 'printf "id    name\\nfixture  %s\\n" "$2"\n',
        'macros': 'printf "fixture aggregate %s\\n" "$*"\n',
        'macros-details': 'printf "fixture itemized %s\\n" "$*"\n',
        'morning-brief': '[[ "$MORNING_BRIEF_DELIVERY" = stdout ]]\nprintf "Fixture brief\\n"\n',
    }
    for name, body in scripts.items():
        script = task_dir / name
        script.write_text('#!/usr/bin/env bash\nset -eu\n' + body)
        script.chmod(0o700)
    # Inject hostile caller secrets, then verify direct plugin child filtering.
    os.environ.update(TELEGRAM_BOT_TOKEN='synthetic-token-not-real', OPENAI_API_KEY='synthetic-key-not-real',
                      PI_CODING_AGENT_DIR='/inaccessible/profile', CLAUDE_CONFIG_DIR='/inaccessible/profile')
    search = load('native_search', 'plugins/search/__init__.py')
    macros = load('native_macros', 'plugins/macros/__init__.py')
    for module in [search, macros]:
        child = module._subprocess_environment(vault, Path('/tmp/fixture-home'))
        assert not any(k.startswith(('PI_', 'CLAUDE_')) or k.endswith(('TOKEN', 'API_KEY')) for k in child)
        assert child['MISE_AUTO_INSTALL'] == '0' and child['UV_OFFLINE'] == '1'
        assert child['TZDIR'] == os.environ['TZDIR'] and child['TZ'] == 'America/New_York'
        assert run(['date', '-d', '2026-10-11 00:00:00 UTC', '+%F'], env=child).stdout == b'2026-10-10\n'
        assert '/usr/local' not in child['PATH'] and '/usr/bin' not in child['PATH']
    for args in ['', 'unknown test', 'food --bad test', 'food --nutrition --nutrition test', 'food "unterminated', 'food ' + 'x' * 513]:
        assert isinstance(search._parse_request(args), str)
    query = 'two words; $(touch /tmp/injection)'
    parsed = search._parse_request('food --nutrition "' + query + '"')
    assert parsed == ('food', query, True)
    result = asyncio.run(search._handle_search('food --nutrition "' + query + '"'))
    assert result.startswith('```\n') and query in result and not Path('/tmp/injection').exists()
    assert len(search._format_output(b'wide line\n' * 2000)) <= 3800
    assert macros._parse_request('') == (('macros',), 'aggregate')
    assert macros._parse_request('2026-10-09') == (('macros', '--', '2026-10-09'), 'aggregate')
    assert macros._parse_request('2026-10-09 "morning snack"') == (('macros-details', '--', '--date', '2026-10-09', '--meal', 'morning snack'), 'itemized')
    for args in ['--bad', 'dinner --bad', '2026-02-30', '"unterminated']:
        assert isinstance(macros._parse_request(args), str)
    assert asyncio.run(macros._handle_macros('2026-10-09')).startswith('fixture aggregate 2026-10-09')
    assert asyncio.run(macros._handle_macros('2026-10-09 "morning snack"')).startswith('fixture itemized --date 2026-10-09 --meal morning snack')
    # Real timeout/child process-group cancellation on a disposable process.
    for module, exception in [(search, search.SearchTimeoutError), (macros, macros.MacrosTimeoutError)]:
        try:
            asyncio.run(module._run_process(['/nix/store/' + Path(shutil.which('sleep')).relative_to('/nix/store').as_posix(), '5'],
                                           cwd=vault, env=module._subprocess_environment(vault, Path('/tmp/fixture-home')), timeout=0.05))
        except exception:
            pass
        else:
            raise AssertionError('timeout missing')
    print('PASS direct zero-model /search and /macros: installed mise dispatch, argv/no shell, child credential filtering, negative grammar, output limit, 10s/15s timeout contracts')

    from importlib.machinery import SourceFileLoader
    food = SourceFileLoader('native_food', str(ASSETS / 'skills/health/food/scripts/adjust-food-log')).load_module()
    original = ('# Synthetic daily note\n\n## Nutrition\n### Nutrition Log\n'
                '> - [meal:: Dinner] [food:: old] [amount:: 1] [unit:: serving] [calories:: 500] '
                '[protein_g:: 20] [carbs_g:: 30] [fat_g:: 10] [fiber_g:: 5]\n'
                '### Daily Totals\nold totals\n## Tasks\nunchanged task\n')
    replacement = original.splitlines()[4].replace('food:: old', 'food:: new').replace('calories:: 500', 'calories:: 400')
    note = vault / 'journal/2026-10-09.md'
    note.parent.mkdir()
    note.write_text(original)
    assert food.atomic_adjust(note, 'Dinner', 'old', replacement) == 'adjusted'
    adjusted = note.read_text()
    assert 'nutrition_calories:: 400' in adjusted and adjusted.endswith('## Tasks\nunchanged task\n')
    inode_mtime = (note.stat().st_ino, note.stat().st_mtime_ns)
    assert food.atomic_adjust(note, 'Dinner', 'old', replacement) == 'already adjusted'
    assert inode_mtime == (note.stat().st_ino, note.stat().st_mtime_ns)
    assert food.atomic_adjust(note, 'Dinner', 'new', None, True) == 'removed'
    assert 'nutrition_calories:: 0' in note.read_text()
    assert food.atomic_adjust(note, 'Dinner', 'new', None, True) == 'already removed'
    ambiguous = original.replace('### Daily Totals', original.splitlines()[4] + '\n### Daily Totals')
    try:
        food.transform_note(ambiguous, 'Dinner', None, replacement)
    except SystemExit:
        pass
    else:
        raise AssertionError('ambiguous food accepted')
    for value in ['nan', '-1', 'inf', 'bad']:
        try:
            food.numeric(value, '--calories')
        except SystemExit:
            pass
        else:
            raise AssertionError('invalid nutrition accepted')
    corrupt = original.replace('### Daily Totals', original.splitlines()[4].replace('meal:: Dinner', 'meal:: Breakfast').replace('calories:: 500', 'calories:: nan') + '\n### Daily Totals')
    note.write_text(corrupt)
    try:
        food.atomic_adjust(note, 'Dinner', 'old', replacement)
    except SystemExit:
        pass
    else:
        raise AssertionError('corrupt existing nutrition accepted')
    assert note.read_text() == corrupt
    note.write_text(original)
    linked_note = vault / 'journal/linked.md'
    linked_note.symlink_to(note)
    hardlinked_note = vault / 'journal/hardlinked.md'
    os.link(note, hardlinked_note)
    for candidate in [linked_note, hardlinked_note]:
        try:
            food.atomic_adjust(candidate, 'Dinner', 'old', replacement)
        except SystemExit:
            pass
        else:
            raise AssertionError('linked food note accepted')
    assert note.read_text() == original
    print('PASS reviewed live food correction/removal helper: fixture atomic replacement, totals, prior-day fixture, identical retry/removal no-op, ambiguous/numeric/linked-file refusal, corrupt input preserved, unrelated section preserved (task/readback parity NOT asserted)')

    # The brief child owns no delivery. Staging scheduler is never run.
    brief_env = dict(os.environ)
    for key in ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'PI_CODING_AGENT_DIR', 'CLAUDE_CONFIG_DIR']:
        brief_env.pop(key)
    result = run(['bash', str(ASSETS / 'morning-brief.sh')], env=brief_env)
    assert result.stdout == b'Fixture brief\n'
    refused = run(['bash', str(ASSETS / 'morning-brief.sh')], env=dict(brief_env, HERMES_NATIVE_OFFLINE='0'), ok=False)
    assert refused.returncode == 64
    from cron.jobs import compute_next_run
    from datetime import timezone
    zone = ZoneInfo('America/New_York')
    # Test Hermes's actual wall-clock/DST wrapper, not bare croniter (which is
    # deliberately corrected by the pinned upstream compute_next_run helper).
    for start, offsets in [('2026-03-07T06:00:00', [-4, -4]), ('2026-10-31T06:00:00', [-5, -5])]:
        previous = datetime.fromisoformat(start).replace(tzinfo=zone)
        for offset in offsets:
            value = datetime.fromisoformat(compute_next_run(jobs[0]['schedule'], previous.astimezone(timezone.utc).isoformat()))
            assert value.hour == 5 and value.utcoffset().total_seconds() == offset * 3600
            assert value.timestamp() > previous.timestamp()
            previous = value
    print('PASS brief stdout-only synthetic task, offline refusal, actual installed Hermes next-run computation: New York 5AM spring/fall DST from UTC anchors; production schedule and delivery INACTIVE')

    # Negative reconciliation: target drift is preserved, never discarded.
    target = state / 'skills/health/macros/SKILL.md'
    target.write_text(target.read_text() + '\nSynthetic reviewed proposal drift.\n')
    drift = target.read_bytes()
    try:
        reconcile.reconcile(state, ASSETS)
    except ValueError:
        pass
    else:
        raise AssertionError('mirror drift overwritten')
    assert target.read_bytes() == drift
    # Exercise the actual native exporter, not a handcrafted manifest. Proposal
    # validation text stays inert; no repository, Git, commit or deploy authority.
    proposal_argv = [sys.executable, '-I', str(ASSETS / 'proposal-create.py'),
                     '--id', 'synthetic-native-proposal', '--title', 'Synthetic native help change',
                     '--rationale', 'Synthetic fixture clarifies a reviewed command help description.',
                     '--test', 'touch /tmp/proposal-tests-must-not-run',
                     '--file', 'skills/health/macros/SKILL.md']
    run(proposal_argv, env=brief_env)
    proposal = vault / 'tools/hermes-handoff/proposals/synthetic-native-proposal'
    manifest = json.loads((proposal / 'manifest.json').read_text())
    assert manifest['schema_version'] == 2 and manifest['owner'] == 'system-config'
    assert manifest['files'][0]['target'] == 'modules/home-manager/hermes-native/skills/health/macros/SKILL.md'
    assert not Path('/tmp/proposal-tests-must-not-run').exists()
    assert run(proposal_argv, env=brief_env, ok=False).returncode != 0
    target.write_bytes(drift + b'\napi_key = sk-syntheticfixtureabcdefghijklmnopqrstuv\n')
    bad_argv = [v.replace('synthetic-native-proposal', 'synthetic-secret-refusal') for v in proposal_argv]
    assert run(bad_argv, env=brief_env, ok=False).returncode != 0
    assert not (vault / 'tools/hermes-handoff/proposals/synthetic-secret-refusal').exists()
    print('PASS actual native proposal exporter: owner/target/base hashes, atomic publish, duplicate/secret refusal, inert validation text; human reviewer/exact-commit gates tested separately')
    link = state / 'linked-file'
    link.symlink_to(target)
    try:
        reconcile.safe(link)
    except ValueError:
        pass
    else:
        raise AssertionError('symlink accepted')
    print('PASS drift and symlink refusal; private/custom skill non-adoption; unsupported Messages remains disabled')
    print('SKIPPED external vault task parity and private six-skill discovery in this fixed check: use the separate operator-only disposable suite. Provider/auth/production vault/Syncthing/Telegram/delivery and individual private-skill enabling remain unproven/disabled; NOT production-ready')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Only reviewed code locations, never exception values, private content,
        # plugin stderr, env, or a full traceback.
        import traceback
        frames = traceback.extract_tb(error.__traceback__)
        locations = ','.join(str(frame.lineno) for frame in frames if frame.filename == __file__)
        raise SystemExit('FAIL fixed offline capability check (' + type(error).__name__ + '; check.py lines ' + locations + '); no readiness claim')
