#!/usr/bin/env python3
"""Narrow native compatibility; shared vault task bodies remain user-owned."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


def main():
    loader, libraries, release, *args = sys.argv[1:]
    # The reviewed shared weight helper removes the old line but leaves its blank
    # separator, adding a blank on every identical retry. Avoid that redundant
    # invocation without forking or mutating the user's shared task/helper.
    weight = None
    if len(args) == 4 and args[:3] == ['run', 'log-weight', '--']:
        weight = args[3]
    elif len(args) == 3 and args[:2] == ['run', 'log-weight']:
        weight = args[2]
    if weight is not None:
        root = Path(os.environ.get('VAULT_DIR', '/nonexistent'))
        state = os.environ.get('HERMES_HOME', '')
        staging = (os.environ.get('HERMES_NATIVE_OFFLINE') == '1'
                   and os.environ.get('HERMES_NATIVE_STAGE') == 'capabilities-offline'
                   and state.startswith('/home/johna/.local/state/hermes-native/staging/'))
        production = (os.environ.get('HERMES_NATIVE_STAGE') == 'production'
                      and os.environ.get('HERMES_PRODUCTION_WRITER_HELD') == '1'
                      and state.endswith('/hermes-native/production/baseline-0.21.2'))
        if (not (staging or production)
                or str(root) != state + '/workspace/notes'
                or any(p.is_symlink() for p in [root, *root.parents])):
            return 64
        if re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', weight):
            date = datetime.now(ZoneInfo('America/New_York')).date().isoformat()
            relative = 'journal/' + date + '.md'
            note = root / relative
            if note.exists():
                if (any(p.is_symlink() for p in [note, *note.parents])
                        or not note.is_file() or note.stat().st_nlink != 1):
                    return 64
                result = subprocess.run(['vlt', 'vault=Personal', 'read', 'file=' + relative],
                                        capture_output=True, text=True, timeout=15)
                lines = [line for line in result.stdout.splitlines() if line.startswith('- weight:: ')]
                if result.returncode == 0 and lines == ['- weight:: ' + weight]:
                    print('Weight already present in ' + date)
                    return 0
    os.execv(loader, [loader, '--library-path', libraries, '--argv0', 'mise', release, *args])


if __name__ == '__main__':
    raise SystemExit(main())
