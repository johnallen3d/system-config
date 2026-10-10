#!/usr/bin/env python3
"""Ensure macOS apply selects its own checkout/worktree, not primary HOME edits."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='nix worktree ') as tmp:
    root = Path(tmp) / 'isolated worktree'
    task = root / '.mise/tasks/nix-rebuild'
    task.parent.mkdir(parents=True)
    shutil.copy2(ROOT / '.mise/tasks/nix-rebuild', task)
    tools = Path(tmp) / 'tools'
    tools.mkdir()
    for name in ('sudo', 'launchctl', 'nix'):
        mock = tools / name
        mock.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                        'with open(os.environ["CALLS"],"a") as f: '
                        'f.write(json.dumps(sys.argv)+"\\n")\n')
        mock.chmod(0o755)
    calls = Path(tmp) / 'calls'
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'],
               CALLS=str(calls), usage_switch_only='true')
    result = subprocess.run(['bash', str(task)], cwd=Path(tmp), env=env,
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    sudo = next(call for call in recorded if Path(call[0]).name == 'sudo')
    assert sudo[1:] == ['darwin-rebuild', 'switch', '--impure', '--flake', f'path:{root}'], sudo
    assert not any(Path(call[0]).name == 'nix' for call in recorded), recorded
    assert 'nix-rebuild log:' in result.stderr
    print('PASS --switch-only applies invoking checkout, includes new files, skips input updates')
