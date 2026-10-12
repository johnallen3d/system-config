#!/usr/bin/env python3
"""Vault editing regressions; Linux integration uses synthetic notes only."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vault_runtime', ROOT / 'modules/home-manager/hermes-native/production-runtime.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
a = r.vlt_adapter()


class Parsing(unittest.TestCase):
    def test_normal_commands_and_literal_multiline_content(self):
        for action in ('write', 'append', 'prepend', 'create', 'patch', 'property:set', 'property:remove', 'search', 'uri'):
            args = {'create': ['name=New', 'path=inbox/New.md', 'content=hello'],
                    'patch': ['file=Note', 'heading=Section', 'content=hello'],
                    'property:set': ['file=Note', 'name=status', 'value=active'],
                    'property:remove': ['file=Note', 'name=status'],
                    'search': ['query=hello'], 'uri': ['file=Note']}.get(action, ['file=Note', 'content=hello'])
            cmd = shlex.join(['vlt', 'vault=Personal', action, *args])
            self.assertEqual(r.terminal_request({'command': cmd})['operation'], 'vault')
        content = '# Text\n\n`code`; $(not-a-shell) && more\n'
        cmd = shlex.join(['vlt', 'vault=Personal', 'write', 'file=Note', 'content=' + content])
        request = r.terminal_request({'command': cmd})
        self.assertEqual(a.parse(r, request['args'])[1]['content'], content)

    def test_confinement_not_a_shell(self):
        for cmd in ('vlt vault=Other write file=Note content=x',
                    'vlt vault=Personal write file=../secret content=x',
                    'vlt vault=Personal write file=/etc/passwd content=x',
                    'vlt vault=Personal write file=.mise/tasks/script content=x',
                    'vlt vault=Personal create name=x path=.config/x.md content=x',
                    'vlt vault=Personal write file=Note',
                    'vlt vault=Personal write file=Note content=x content=y',
                    'vlt vault=Personal write file=Note content=x && rm -rf /',
                    'bash -c true'):
            with self.subTest(cmd=cmd), self.assertRaises(ValueError):
                r.terminal_request({'command': cmd})

    def test_exact_and_unique_title_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp).resolve()
            (vault / 'notes').mkdir(); (vault / 'notes/Note.md').write_text('synthetic')
            self.assertEqual(a.note_target(r, vault, 'write', {'file': 'Note'}), 'notes/Note.md')
            (vault / 'other').mkdir(); (vault / 'other/Note.md').write_text('synthetic')
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                a.note_target(r, vault, 'write', {'file': 'Note'})
            self.assertEqual(a.note_target(r, vault, 'write', {'file': 'notes/Note.md'}), 'notes/Note.md')
            (vault / 'notes/link.md').symlink_to(vault / 'notes/Note.md')
            with self.assertRaises(ValueError):
                a.note_target(r, vault, 'write', {'file': 'notes/link.md'})


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('HERMES_VLT_FIXTURE_METADATA'),
                     'installed Linux sandbox integration')
class Installed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hermes-vlt-fixture-')
        root = Path(self.tmp.name).resolve()
        self.state = root / 'hermes-native/production/baseline-0.21.2'
        self.state.mkdir(parents=True, mode=0o700)
        self.vault = root / 'vault'; self.vault.mkdir(mode=0o700)
        self.m = json.loads(Path(os.environ['HERMES_VLT_FIXTURE_METADATA']).read_text())
        self.m['paths']['state'] = str(self.state); self.m['vault'] = str(self.vault)
        self.m['environment'] = dict(self.m['environment'], HERMES_HOME=str(self.state))
        for n in ('home', 'config', 'cache'):
            q = root / n; q.mkdir(mode=0o700); self.m['paths'][n] = str(q)
        r.initialize(self.m)
        owner = r.t.load(self.state / 'controller/ownership.json')
        owner.update(owner='native', phase='NATIVE_LIVE', vaultWrites='ENABLED', poller='ENABLED',
                     normalWriterPolicy='NAS_NORMAL_NONOVERLAP_POLICY_CONTINUATION')
        r.p.stage.atomic(self.state / 'controller/ownership.json', r.p.stage.encoded(owner))
        (self.vault / 'notes').mkdir(mode=0o700)
        (self.vault / 'notes/Note.md').write_text('---\nstatus: draft\n---\n# Synthetic\n\n## Section\n\nOriginal\n')
        (self.vault / 'notes/Sibling.md').write_text('KEEP SIBLING\n')
        (self.vault / 'AGENTS.md').write_text('KEEP ROOT\n')
        (self.vault / 'CLAUDE.md').symlink_to('AGENTS.md')
        self.scanned = []

    def tearDown(self): self.tmp.cleanup()

    def observe(self, names):
        return {'folder': 'notes', 'type': 'sendreceive', 'state': 'idle', 'observedAt': time.time(),
                'localConvergence': True, 'directPeerConvergence': True, 'directPeerCount': 1,
                'conflicts': 0, 'temporary': 0, 'special': 0}

    def run_vlt(self, action, *args):
        try:
            return a.run(r, self.m, ['vault=Personal', action, *args],
                         observer=self.observe, scan=lambda names: self.scanned.extend(names))
        except Exception:
            for f in (self.state / 'controller/vlt-runs').glob('*/stderr'):
                if f.stat().st_size: print('SYNTHETIC STDERR:', f.read_text()[-1500:])
            raise

    def test_actual_mutations_reads_and_frontmatter(self):
        self.run_vlt('write', 'file=Note', 'content=# New\n\n## Section\n\nNew body\n')
        self.assertIn('status: draft', (self.vault / 'notes/Note.md').read_text())
        self.run_vlt('append', 'file=notes/Note.md', 'content=Appended literal `code`\n')
        self.run_vlt('prepend', 'file=Note', 'content=Prepended\n')
        self.run_vlt('patch', 'file=Note', 'old=New body', 'new=Patched body')
        self.run_vlt('property:set', 'file=Note', 'name=status', 'value=active')
        self.run_vlt('property:remove', 'file=Note', 'name=status')
        content = (self.vault / 'notes/Note.md').read_text()
        self.assertIn('Patched body', content); self.assertIn('Prepended', content)
        self.assertNotIn('status:', content)
        self.assertIn(b'Patched body', self.run_vlt('read', 'file=notes/Note.md'))
        self.assertIn(b'Note', self.run_vlt('search', 'query=Patched'))
        self.assertIn(b'obsidian://', self.run_vlt('uri', 'file=Note'))
        self.assertEqual((self.vault / 'notes/Sibling.md').read_text(), 'KEEP SIBLING\n')
        self.assertEqual((self.vault / 'AGENTS.md').read_text(), 'KEEP ROOT\n')
        self.assertEqual(r.t.load(self.state / 'writer-reservation.json')['status'], 'COMPLETE')
        self.assertFalse((self.vault / '.vlt.lock').exists())

    def test_create_root_and_missing_nested_folders(self):
        for path in ('New.md', 'new-folder/nested/New.md'):
            self.run_vlt('create', 'name=New', 'path=' + path, 'content=# Created\n')
            self.assertEqual((self.vault / path).read_text(), '# Created\n')
            self.run_vlt('append', 'file=' + path, 'content=Root and nested updates work\n')
            self.assertIn(b'updates work', self.run_vlt('read', 'file=' + path))
            self.assertIn(b'obsidian://', self.run_vlt('uri', 'file=' + path))
        self.assertEqual((self.vault / 'notes/Sibling.md').read_text(), 'KEEP SIBLING\n')

    def test_failed_edit_is_noeffect_not_gateway_revocation(self):
        before = (self.vault / 'notes/Note.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'no vault change'):
            self.run_vlt('patch', 'file=Note', 'heading=Missing heading', 'content=nope')
        self.assertEqual((self.vault / 'notes/Note.md').read_bytes(), before)
        self.assertEqual(r.t.load(self.state / 'writer-reservation.json')['status'], 'COMPLETE')
        self.run_vlt('append', 'file=Note', 'content=Still works')

    def test_conflict_and_cas_checks_precede_real_commit(self):
        before = (self.vault / 'notes/Note.md').read_bytes()
        with mock.patch.object(self, 'observe', return_value={**self.observe(()), 'conflicts': 1}), self.assertRaises(ValueError):
            self.run_vlt('write', 'file=Note', 'content=No commit')
        self.assertEqual((self.vault / 'notes/Note.md').read_bytes(), before)
        self.assertFalse((self.state / 'writer-reservation.json').exists())


if __name__ == '__main__': unittest.main()
