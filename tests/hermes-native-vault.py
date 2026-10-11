#!/usr/bin/env python3
"""Operator-only #758 fixture suite; never adds an unrestricted launcher route.

Reviewed external task CODE is provided in a private allowlisted directory. No
production notes, profiles, credentials or private skills enter Nix/Git. Runs in
fresh mount/network/PID namespaces with only store packages and reviewed inputs.
Provider fixtures are explicitly synthetic; no auth/API parity is claimed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

TASKS = ('common-food', 'common-foods-browser', 'macros', 'macros-details',
         'write-food-log', 'activity-log', 'log-weight', 'add-list-item',
         'recipe-table', 'ocr-label', 'morning-brief', 'lib-vlt-note.sh',
         'vault-note-rmw.py', 'daily-path', 'strip-journal-leading-blank-line')
INPUTS = tuple('.mise/tasks/' + name for name in TASKS) + ('scripts/macros', 'scripts/macros-details')
FAILURES = []


def run(argv, *, env=None, ok=True, timeout=60):
    result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=timeout)
    if ok and result.returncode:
        raise RuntimeError('fixture command exit ' + str(result.returncode) + ': ' + result.stderr[-1200:])
    return result


def case(name, function):
    try:
        function()
    except Exception as error:
        FAILURES.append(name)
        # Only synthetic fixtures can be executed here. Never print private inputs.
        print('FAIL ' + name + ': ' + type(error).__name__ + ' ' + str(error)[:1400], flush=True)
    else:
        print('PASS ' + name, flush=True)


def inside(metadata):
    assert os.environ['HERMES_NATIVE_OFFLINE'] == '1'
    assert not Path('/home/johna/notes').exists() and not Path('/Users').exists()
    assert not any(k.startswith(('PI_', 'CLAUDE_')) or k.endswith(('TOKEN', 'API_KEY')) for k in os.environ)
    state = Path(os.environ['HERMES_HOME'])
    vault = state / 'workspace/notes'
    for p in [state, vault, Path(os.environ['HOME']), Path(os.environ['XDG_CONFIG_HOME']), Path(os.environ['XDG_CACHE_HOME'])]:
        p.mkdir(parents=True, mode=0o700, exist_ok=True)
    source = Path('/fixture-sources')
    hashes = json.loads((source / 'hashes.json').read_text())
    assert set(hashes) == set(INPUTS)
    for name in INPUTS:
        p = source / name
        assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest() == hashes[name]
        target = vault / name
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        target.write_bytes(p.read_bytes())
        target.chmod(0o700)
    os.chdir(vault)
    os.environ.update(VAULT_DIR=str(vault), VLT_VAULT_PATH=str(vault), VLT_VAULT='Personal', VAULT_NAME='Personal',
                      MISE_TRUSTED_CONFIG_PATHS=str(vault), MORNING_BRIEF_DELIVERY='stdout', MORNING_BRIEF_INCLUDE_FLIGHTS='0')
    for relative in ['.obsidian', 'journal', 'templates', 'health', 'lists', 'recipes']:
        (vault / relative).mkdir(exist_ok=True)
    (vault / '.obsidian/app.json').write_text('{}\n')
    today = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    # The actual vault tasks use libc/GNU date, not Python's packaged zoneinfo.
    # Catch the sealed-namespace UTC fallback even before implicit-date writers.
    assert run(['date', '-d', '2026-10-11 00:00:00 UTC', '+%F %z']).stdout.strip() == '2026-10-10 -0400'
    assert run(['date', '+%F']).stdout.strip() == today
    relative = 'journal/' + today + '.md'
    note = vault / relative
    template = ('# ' + today + '\n\n## Tasks\n\n- [ ] KEEP TASK\n\n## Misc\n\nKEEP MISC\n\n'
                '## Nutrition\n\n### Daily Totals\n\n### Nutrition Log\n\n> [!note]- Raw nutrition entries\n>\n'
                '### Nutrition Summary\n\n![[nutrition-summary]]\n\n## Activity\n\n'
                '### Activity Log\n\n> [!note]- Raw activity entries\n>\n### Activity Summary\n\n'
                '![[activity-summary]]\n\n## Captures\n\nKEEP CAPTURE\n\n## Pi Log\n\nKEEP LOG\n')
    (vault / 'templates/journal.md').write_text(template)
    note.write_text(template)
    for name in ['tasks', 'shopping', 'groceries']:
        (vault / ('lists/' + name + '.md')).write_text('# Fixture list\n\nKEEP LIST\n')

    def task(name, *args, **kwargs):
        return run([os.environ['HERMES_NATIVE_MISE'], 'run', name, '--', *args], **kwargs)

    def acknowledge():
        run(['vlt', 'vault=Personal', 'integrity:acknowledge', 'file=' + relative])

    def read():
        return run(['vlt', 'vault=Personal', 'read', 'file=' + relative]).stdout

    def unchanged_after(command):
        before = (note.read_bytes(), note.stat().st_mtime_ns)
        command()
        assert (note.read_bytes(), note.stat().st_mtime_ns) == before, 'retry changed note bytes/mtime'

    case('native vlt headless disposable path/readback', lambda: (read() == note.read_text()) or (_ for _ in ()).throw(AssertionError('vlt read mismatch')))
    py = os.environ['HERMES_NATIVE_TASK_PYTHON']

    def closure():
        run([py, '-I', '-c', 'import yaml, PIL, pillow_heif, reportlab, pypdf, playwright; assert yaml.__version__ == "6.0.2"'])
        assert '0.8.2' in run(['uvx', '--from', 'notebooklm-py[browser]==0.8.2', 'notebooklm', '--version']).stdout
        run(['notebooklm', 'login', '--help'])
        # Generate explicitly synthetic input images and a text PDF, offline.
        code = '''from PIL import Image,ImageDraw,ImageFont
import os,pillow_heif
from reportlab.pdfgen import canvas
pillow_heif.register_heif_opener()
i=Image.new('RGB',(1200,500),'white');d=ImageDraw.Draw(i);f=ImageFont.truetype(os.environ['HERMES_NATIVE_FONT'],60)
d.multiline_text((35,35),'NUTRITION FACTS\\nCalories 250\\nProtein 20 g',font=f,fill='black',spacing=30)
i.save('/tmp/fixture.png');i.save('/tmp/fixture.heic',format='HEIF',quality=100)
c=canvas.Canvas('/tmp/fixture.pdf');c.drawString(72,720,'Synthetic nutrition Calories 250 Protein 20 g');c.save()
'''
        run([py, '-I', '-c', code])
        pdf = run(['pdftotext', '/tmp/fixture.pdf', '-']).stdout
        assert 'Calories 250' in pdf and 'Protein 20 g' in pdf
    case('pinned NotebookLM0.8.2/browser imports, exact PyYAML6.0.2 and PDF fixture', closure)

    def extraction():
        path = Path('/tmp/fixture-article.html')
        path.write_text('<!doctype html><html><head><title>Synthetic native article</title></head><body>'
                        '<nav>UNRELATED NAVIGATION</nav><article><h1>Synthetic native article</h1>' +
                        '<p>Deterministic offline extraction preserves synthetic nutrition values 250 calories and 20 g protein.</p>' * 8 +
                        '</article></body></html>')
        text = run(['defuddle', 'parse', str(path), '--markdown']).stdout
        assert '250 calories and 20 g protein' in text and 'UNRELATED NAVIGATION' not in text
        assert run(['defuddle', 'parse', '/tmp/missing-article.html', '--markdown'], ok=False).returncode != 0
    case('actual pinned Defuddle local HTML-to-Markdown extraction and missing-input refusal; no network', extraction)

    def ocr():
        for path in ['/tmp/fixture.png', '/tmp/fixture.heic']:
            text = task('ocr-label', path, timeout=90).stdout
            assert '250' in text and '20' in text, 'OCR lost synthetic label numbers'
        assert task('ocr-label', '/tmp/missing.png', ok=False).returncode != 0
    case('actual native OCR task including HEIC conversion and missing-input refusal', ocr)

    food = {'id': 'fixture-yogurt', 'name': 'Fixture Greek yogurt', 'category': 'breakfast', 'aliases': ['fixture breakfast'],
            'serving': {'amount': 1, 'unit': 'serving', 'label': '1 serving'},
            'nutrition': {'calories': 250, 'protein_g': 20, 'carbs_g': 30, 'fat_g': 8, 'fiber_g': 4}, 'notes': 'SYNTHETIC ONLY'}
    (vault / 'health/common-foods.yaml').write_text(json.dumps({'foods': [food]}))
    (vault / 'health/common-foods-browser.html').write_text('<!doctype html><title>Fixture</title>')

    def common_food():
        task('common-food', 'validate')
        search = task('common-food', 'search', 'fixture', '--nutrition').stdout
        assert 'fixture-yogurt' in search and '250' in search and '20' in search
        assert 'fixture-yogurt' in task('common-food', 'show', 'fixture-yogurt').stdout
        assert 'fixture-yogurt' not in task('common-food', 'search', 'nomatch').stdout
        assert task('common-food', 'invalid', ok=False).returncode != 0
        task('common-foods-browser')
        html = (vault / 'health/common-foods-browser.html').read_text()
        assert 'Fixture Greek yogurt' in html and '<title>Common Foods Browser</title>' in html
    case('actual common-food yq/column search/show/validate and exact-PEP723 browser HTML writer', common_food)

    food_args = ['--date', today, '--meal', 'dinner', '--food', 'fixture-yogurt', '--amount', '1', '--unit', 'serving',
                 '--calories', '250', '--protein-g', '20', '--carbs-g', '30', '--fat-g', '8', '--fiber-g', '4', '--source', 'common']

    def food_write():
        task('write-food-log', *food_args)
        text = read()
        assert text.count('[food:: fixture-yogurt]') == 1
        assert 'nutrition_calories:: 250' in text and all(x in text for x in ['KEEP TASK', 'KEEP MISC', 'KEEP CAPTURE', 'KEEP LOG'])
        unchanged_after(lambda: task('write-food-log', *food_args))
        assert task('write-food-log', '--meal', 'dinner', ok=False).returncode != 0
    case('actual food writer/readback/totals/retry and required-field refusal', food_write)

    def reports():
        before = note.read_bytes()
        assert 'Calories: 250 kcal' in task('macros', today).stdout
        assert '250 kcal' in task('macros-details', '--date', today, '--meal', 'dinner').stdout
        assert 'fixture-yogurt' in task('macros-details', '--date', today).stdout
        assert task('macros-details', '--date', '2026-02-30', ok=False).returncode != 0
        assets = Path(metadata['managedAssets'])
        for name in ['search', 'macros']:
            spec = importlib.util.spec_from_file_location('fixture_' + name, assets / ('plugins/' + name + '/__init__.py'))
            module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            if name == 'search':
                assert 'fixture-yogurt' in asyncio.run(module._handle_search('food --nutrition fixture'))
            else:
                assert asyncio.run(module._handle_macros(today)) == task('macros', today).stdout
                assert asyncio.run(module._handle_macros(today + ' dinner')) == task('macros-details', '--date', today, '--meal', 'dinner').stdout
        assert note.read_bytes() == before
    case('actual aggregate/itemized tasks and direct plugin stdout parity; reports read-only', reports)

    def correction():
        helper = Path(metadata['managedAssets']) / 'skills/health/food/scripts/adjust-food-log'
        args = [sys.executable, '-I', str(helper), *food_args, '--match-food', 'fixture-yogurt']
        args[args.index('--food') + 1] = 'fixture-corrected'
        args[args.index('--calories') + 1] = '200'
        run(args);acknowledge()
        assert '[food:: fixture-corrected]' in read() and 'nutrition_calories:: 200' in read()
        unchanged_after(lambda: run(args))
        remove = [sys.executable, '-I', str(helper), '--date', today, '--meal', 'dinner', '--match-food', 'fixture-corrected', '--remove']
        run(remove);acknowledge();assert 'nutrition_calories:: 0' in read()
        unchanged_after(lambda: run(remove))
    case('reviewed native food helper actual CLI/vlt correction-removal/readback/retries', correction)

    def activity():
        args = ['--date', today, '--time', '16:15', 'incline walk 5%, 30m, 3mph']
        task('activity-log', *args);text = read()
        assert float(re.search(r'\[duration_min:: ([^\]]+)\]', text).group(1)) == 30
        assert float(re.search(r'\[speed_mph:: ([^\]]+)\]', text).group(1)) == 3 and 'KEEP LOG' in text
        unchanged_after(lambda: task('activity-log', *args))
        assert task('activity-log', '--time', '25:00', 'walk', ok=False).returncode != 0
    case('actual activity writer/vlt readback/retry and invalid-time refusal', activity)

    def weight():
        task('log-weight', '180.5');assert '- weight:: 180.5' in read()
        assert task('log-weight', 'not-numeric', ok=False).returncode != 0
        unchanged_after(lambda: task('log-weight', '180.5'))
        for override in [{'HERMES_NATIVE_OFFLINE': '0'}, {'HERMES_NATIVE_STAGE': 'foundation'},
                         {'VAULT_DIR': '/home/johna/notes'}]:
            before = (note.read_bytes(), note.stat().st_mtime_ns)
            assert task('log-weight', '180.5', env=dict(os.environ, **override), ok=False).returncode != 0
            assert (note.read_bytes(), note.stat().st_mtime_ns) == before
        task('log-weight', '181');assert '- weight:: 181' in read() and '- weight:: 180.5' not in read()
        unchanged_after(lambda: task('log-weight', '181'))
        saved = note.with_suffix('.saved');note.rename(saved);note.symlink_to(saved)
        try:
            assert task('log-weight', '181', ok=False).returncode != 0
        finally:
            note.unlink();saved.rename(note)
    case('actual weight first-write/readback/invalid-input; native identical-retry no-op and negative gates', weight)

    def lists():
        for name in ['tasks', 'shopping', 'groceries', 'daily']:
            args = ['SYNTHETIC $(touch /tmp/injected) item', name, '--date', today, '--time', '17:00']
            task('add-list-item', *args)
            target = relative if name == 'daily' else 'lists/' + name + '.md'
            text = run(['vlt', 'vault=Personal', 'read', 'file=' + target]).stdout
            assert text.count('SYNTHETIC $(touch /tmp/injected) item') == 1 and not Path('/tmp/injected').exists()
            before = (vault / target).read_bytes();task('add-list-item', *args)
            assert (vault / target).read_bytes() == before
        assert task('add-list-item', 'item', 'invalid-list', ok=False).returncode != 0
    case('actual task/list/daily writers, vlt readback, retries and argv literal preservation', lists)

    def recipe():
        path = vault / 'recipes/fixture.md'
        original = '# Synthetic recipe\n\n## Ingredients\n\n- 1 cup oats\n- 1 cup water\n\n## Steps\n\n1. Mix oats and water.\n\n## Notes\n\nKEEP RECIPE\n'
        path.write_text(original)
        plan = {'row_order': [0, 1], 'columns': [{'label': 'Mix', 'cells': [{'start': 0, 'end': 1, 'title': 'Mix', 'detail': 'oats and water', 'steps': [1]}]}]}
        Path('/tmp/plan.json').write_text(json.dumps(plan))
        task('recipe-table', 'recipes/fixture.md', '--plan-file', '/tmp/plan.json')
        text = run(['vlt', 'vault=Personal', 'read', 'file=recipes/fixture.md']).stdout
        assert 'Recipe Table' in text and 'rowspan="2"' in text and 'KEEP RECIPE' in text
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        task('recipe-table', 'recipes/fixture.md', '--plan-file', '/tmp/plan.json')
        assert (path.read_bytes(), path.stat().st_mtime_ns) == before
        bad = {'row_order': [0], 'columns': []};Path('/tmp/bad-plan.json').write_text(json.dumps(bad))
        assert task('recipe-table', 'recipes/fixture.md', '--force', '--plan-file', '/tmp/bad-plan.json', ok=False).returncode != 0
        assert path.read_bytes() == before[0]
    case('actual recipe renderer/atomic writer/readback/precomputed plan/retry/refusal; no model calls', recipe)

    def browser():
        code = '''from playwright.sync_api import sync_playwright
import os,glob,pathlib
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,args=['--no-sandbox'])
 page=b.new_page();page.goto(pathlib.Path(os.environ['VAULT_DIR']+'/health/common-foods-browser.html').as_uri())
 assert page.locator('#rows tr').count()==1
 page.locator('#search').fill('nomatch');assert page.locator('#rows tr').count()==0
 page.locator('#clear').click();assert page.locator('#rows tr').count()==1
 b.close()
'''
        result = run([py, '-I', '-c', code], env=dict(os.environ, DEBUG='pw:browser'), ok=False, timeout=90)
        if result.returncode:
            diagnostic = '\n'.join(line for line in result.stderr.splitlines()
                                   if any(word in line.lower() for word in ['fatal', 'crash', 'signal', 'library', 'process exited', 'targetclosederror']))
            raise RuntimeError(diagnostic[:1250] or result.stderr[-1200:])
    case('actual packaged headless Chromium local HTML render/search; no network or personal profile', browser)

    def brief():
        # Only fetch/format providers are fixture adapters. The brief orchestration,
        # shared atomic writer and vlt readback are actual reviewed task bodies.
        providers = {'get-weather': 'Fixture clear 20 C', 'get-calendar': 'Fixture appointment 10:00'}
        for name, text in providers.items():
            p = vault / '.mise/tasks' / name
            p.write_text('#!/usr/bin/env bash\nset -eu\n' +
                         ('[[ "${FIXTURE_CALENDAR_FAIL:-0}" != 1 ]] || exit 31\n' if name == 'get-calendar' else '') +
                         'case "$*" in *--format=json*) printf \'{"fixture":true}\\n\';; *) printf \'%s\\n\' ' + repr(text) + ';; esac\n')
            p.chmod(0o700)
        sentinel = vault / '.mise/tasks/send-telegram'
        sentinel.write_text('#!/usr/bin/env bash\ntouch /tmp/unexpected-delivery\nexit 86\n');sentinel.chmod(0o700)
        output = task('morning-brief').stdout
        text = read()
        assert text.count('## Weather') == 1 and text.count('## Calendar') == 1
        assert all(x in text for x in ['Fixture clear 20 C', 'Fixture appointment 10:00', 'KEEP TASK', 'KEEP MISC', 'KEEP CAPTURE', 'KEEP LOG'])
        assert output.count('Good morning!') == 1 and 'Fetching weather' not in output and not Path('/tmp/unexpected-delivery').exists()
        unchanged_after(lambda: task('morning-brief'))
        unchanged_after(lambda: task('morning-brief', env=dict(os.environ, FIXTURE_CALENDAR_FAIL='1'), ok=False))
        assert task('morning-brief', env=dict(os.environ, FIXTURE_CALENDAR_FAIL='1'), ok=False).returncode != 0
        before = note.read_bytes()
        code = 'source "$VAULT_DIR/.mise/tasks/lib-vlt-note.sh"; atomic_morning_brief_update "$1" /tmp/missing-weather /tmp/missing-calendar 0 /dev/null'
        assert run(['bash', '-c', code, 'fixture', relative], ok=False).returncode != 0
        assert note.read_bytes() == before and not note.with_suffix('.md.tmp').exists()
    case('actual zero-model brief orchestration/atomic writer/vlt readback/retry/failure preservation/stdout-only', brief)
    def actual_local_lock():
        # #759: actual reviewed helper, not the synthetic transaction protocol.
        # It coordinates only processes sharing this namespace's /tmp lock inode.
        import fcntl
        import time
        target = vault / 'journal/local-lock-canary.md'
        target.write_bytes(b'SYNTHETIC BASE\n')
        helper = vault / '.mise/tasks/vault-note-rmw.py'
        lock_id = hashlib.sha256(str(target.resolve()).encode()).hexdigest()[:24]
        lock_path = Path('/tmp') / ('pi-vault-rmw-' + lock_id + '.lock')
        code = ('import importlib.util,sys; from pathlib import Path; '
                's=importlib.util.spec_from_file_location("rmw",sys.argv[1]); '
                'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
                'm.atomic_update(Path(sys.argv[2]),lambda old:(old+sys.argv[3]+"\\n","added"))')
        children = []
        with lock_path.open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                for i in range(8):
                    children.append(subprocess.Popen([py,'-I','-c',code,str(helper),str(target),'SYNTHETIC-'+str(i)], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
                time.sleep(.3)
                assert all(p.poll() is None for p in children) and target.read_bytes() == b'SYNTHETIC BASE\n', 'held stable workflow lock did not block children'
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        for p in children:
            p.communicate(timeout=30)
            assert p.returncode == 0, 'actual lock child failed'
        text = target.read_text()
        assert text.count('SYNTHETIC BASE') == 1 and all(text.count('SYNTHETIC-'+str(i)+'\n') == 1 for i in range(8)), 'serialized helper lost/duplicated local update'
        before = (target.read_bytes(), target.stat().st_mtime_ns)
        fail = ('import importlib.util,sys;from pathlib import Path; '
                's=importlib.util.spec_from_file_location("rmw",sys.argv[1]); '
                'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
                'm.atomic_update(Path(sys.argv[2]),lambda old:(_ for _ in ()).throw(ValueError("synthetic refusal")))')
        assert run([py,'-I','-c',fail,str(helper),str(target)],ok=False).returncode != 0
        assert (target.read_bytes(), target.stat().st_mtime_ns) == before, 'helper refusal changed bytes/mtime'
        assert not list(target.parent.glob('*.tmp')), 'unexpected disposable partial file remains'
    case('actual vault-owned stable lock: eight local same-file writers/no lost update/atomic failure; not distributed authority', actual_local_lock)
    def private_skills():
        root = Path('/private-skills')
        receipt = json.loads((root / 'native-review.json').read_text())
        assert receipt['owner'] == 'private-user-runtime-state' and receipt['enabled'] is False
        assert len(receipt['source_files']) == 9 and len(receipt['individual_gates']) == 6
        from hermes_cli.config import _HERMES_HOME_SUBDIRS
        for directory in _HERMES_HOME_SUBDIRS:
            (state / directory).mkdir(mode=0o700, parents=True, exist_ok=True)
        (state / '.env').write_bytes(b'')
        (state / 'config.yaml').write_text(json.dumps({'_config_version': 44}))
        for name, digest in receipt['source_files'].items():
            source_file = root / name
            assert name.startswith('skills/') and '..' not in Path(name).parts
            assert hashlib.sha256(source_file.read_bytes()).hexdigest() == digest
            target = state / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(source_file.read_bytes())
            target.chmod(0o600)
        spec = importlib.util.spec_from_file_location('fixture_reconcile', Path(metadata['reconciler']))
        reconcile = importlib.util.module_from_spec(spec);spec.loader.exec_module(reconcile)
        reconcile.reconcile(state, Path(metadata['managedAssets']))
        from agent.skill_commands import resolve_skill_command_key
        for name in receipt['individual_gates']:
            assert resolve_skill_command_key(name) == '/' + name
            assert resolve_skill_command_key(name.replace('-', '_')) == '/' + name
        before = {name: (state / name).read_bytes() for name in receipt['source_files']}
        reconcile.reconcile(state, Path(metadata['managedAssets']))
        assert before == {name: (state / name).read_bytes() for name in before}
        assert not json.loads((state / 'config.yaml').read_text())['platforms']['telegram']['enabled']
    case('six private skills/nine companions: isolated actual discovery/aliases/preservation; host remains unregistered', private_skills)
    print('Fixture input SHA receipt: ' + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest())
    print('Provider adapters synthetic; production vault/Syncthing/auth/Telegram/delivery NOT tested or enabled.')
    return 1 if FAILURES else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--private-skills', type=Path)
    parser.add_argument('--inside', action='store_true')
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text())
    assert metadata['stage'] == 'capabilities-offline' and not metadata['gatewayEnabled'] and not metadata['productionStateTransferred']
    if args.inside:
        return inside(metadata)
    assert args.sources is not None
    source = args.sources.absolute()
    assert source.resolve() == source and not source.is_symlink()
    assert source.stat().st_mode & 0o077 == 0
    for name in [*INPUTS, 'hashes.json']:
        p = source / name
        assert not any(q.is_symlink() for q in [p, *p.parents])
        s = p.stat();assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= 262144 and s.st_mode & 0o077 == 0
    assert args.private_skills is not None
    private = args.private_skills.absolute()
    assert private.resolve() == private and private.stat().st_mode & 0o077 == 0
    receipt = json.loads((private / 'native-review.json').read_text())
    for name in [*receipt['source_files'], 'native-review.json']:
        p = private / name
        assert name == 'native-review.json' or (name.startswith('skills/') and '..' not in Path(name).parts)
        assert not any(q.is_symlink() for q in [p, *p.parents])
        s = p.stat();assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size <= 262144 and s.st_mode & 0o077 == 0
    launcher = Path(metadata['launcher']).read_text()
    bwrap = re.findall(r'/nix/store/[^\s]+/bin/bwrap', launcher)[0]
    env = dict(metadata['environment'], HERMES_NATIVE_OFFLINE='1')
    bash = next(p + '/bash' for p in env['PATH'].split(':') if Path(p + '/bash').is_file())
    shell = str(Path(bash).with_name('sh'))
    executable = next(p + '/env' for p in env['PATH'].split(':') if Path(p + '/env').is_file())
    command = [bwrap, '--unshare-all', '--die-with-parent', '--new-session', '--ro-bind', '/nix/store', '/nix/store',
               '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/dev/shm', '--tmpfs', '/tmp', '--tmpfs', '/home', '--dir', '/etc',
               '--dir', '/usr', '--dir', '/usr/bin', '--dir', '/bin', '--symlink', executable, '/usr/bin/env',
               '--symlink', bash, '/bin/bash', '--symlink', shell, '/bin/sh', '--ro-bind', str(source), '/fixture-sources',
               '--ro-bind', str(private), '/private-skills',
               '--ro-bind', str(Path(__file__).absolute()), '/test.py', '--chdir', '/tmp', metadata['python'], '-I', '/test.py',
               '--metadata', str(args.metadata.absolute()), '--inside']
    return subprocess.run(command, env=env, timeout=600).returncode


if __name__ == '__main__':
    raise SystemExit(main())
