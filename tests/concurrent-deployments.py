#!/usr/bin/env python3
"""Real Git worktree/overlay and kernel-lock checks. No Nix activation or commits."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".mise/scripts"))
import deployment_state as state


class Deployment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="concurrent-deployments-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "primary with spaces"
        subprocess.run(["git", "clone", "--quiet", "--shared", "--branch", "main", str(ROOT), str(self.repo)], check=True)
        self.a, self.b = (self.repo / ".worktrees" / name for name in ("task-a", "task-b"))
        for path in (self.a, self.b):
            state.git(self.repo, "worktree", "add", "-b", "feature/" + path.name, str(path), "main")
        self.directory = self.root / "state"
        self.directory.mkdir()
        self.generation = "/nix/store/fixture-initial"
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(state, "current_generation", side_effect=lambda: self.generation).start()
        mock.patch.object(state, "evaluated_generation", side_effect=lambda repo: "/nix/store/fixture-" + state.source_tree(repo)).start()
        self.generation = state.evaluated_generation(self.repo)
        state.adopt(self.repo, self.repo, "main", self.directory)

    def plan(self, path):
        return state.plan(path, self.directory)

    def activate(self, record):
        self.generation = record["generation"]
        state.finish(self.repo, self.directory)

    def test_two_unintegrated_tasks_preserved_without_touching_sources_or_indexes(self):
        (self.a / "active-a").write_bytes(b"\x00\xffalready active task a")
        (self.a / "active-link").symlink_to("active-a")
        first = self.plan(self.a)
        self.activate(first)
        (self.b / "pending-b").write_text("authorized second deployment")
        before = {path: (Path(state.git(path, "rev-parse", "--absolute-git-dir")) / "index").read_bytes() for path in (self.repo, self.a, self.b)}
        tips = [state.git(path, "rev-parse", "HEAD") for path in (self.repo, self.a, self.b)]
        second = self.plan(self.b)
        source = Path(second["source"])
        self.assertEqual((source / "active-a").read_bytes(), b"\x00\xffalready active task a")
        self.assertTrue((source / "active-link").is_symlink())
        self.assertEqual((source / "pending-b").read_text(), "authorized second deployment")
        self.assertFalse((self.b / "active-a").exists())
        self.assertFalse((self.repo / "pending-b").exists())
        self.assertEqual(tips, [state.git(path, "rev-parse", "HEAD") for path in (self.repo, self.a, self.b)])
        for path, data in before.items():
            self.assertEqual((Path(state.git(path, "rev-parse", "--absolute-git-dir")) / "index").read_bytes(), data)
        self.activate(second)
        (self.a / "active-a").write_bytes(b"new owned revision")
        third = self.plan(self.a)
        self.assertEqual((Path(third["source"]) / "active-a").read_bytes(), b"new owned revision")
        self.assertTrue((Path(third["source"]) / "pending-b").exists())

    def test_actual_same_file_conflict_names_owners_and_does_not_change_active(self):
        (self.a / "README.md").write_text("deployed task A change\n")
        first = self.plan(self.a)
        self.activate(first)
        before = (self.directory / "active.json").read_bytes()
        (self.b / "README.md").write_text("incompatible task B change\n")
        with self.assertRaisesRegex(RuntimeError, "README.md.*feature/task-a.*feature/task-b"):
            self.plan(self.b)
        self.assertEqual((self.directory / "active.json").read_bytes(), before)
        self.assertFalse((self.directory / "pending.json").exists())
        self.assertEqual((self.a / "README.md").read_text(), "deployed task A change\n")

    def test_never_collects_unactivated_task_or_later_source_edits(self):
        (self.a / "active-a").write_text("active")
        self.activate(self.plan(self.a))
        (self.a / "not-deployed").write_text("leave pending")
        (self.b / "own-b").write_text("B")
        record = self.plan(self.b)
        self.assertFalse((Path(record["source"]) / "not-deployed").exists())
        self.assertTrue((self.a / "not-deployed").exists())

    def test_unknown_generation_and_edited_snapshot_block(self):
        self.generation = "/nix/store/out-of-band-rollback"
        with self.assertRaisesRegex(RuntimeError, "Unrecorded activation/rollback"):
            self.plan(self.a)
        record = json.loads((self.directory / "active.json").read_text())
        self.generation = record["generation"]
        (Path(record["source"]) / "tampered").write_text("do not reset")
        with self.assertRaisesRegex(RuntimeError, "source was edited"):
            self.plan(self.a)
        self.assertTrue((Path(record["source"]) / "tampered").exists())

    def test_crash_after_activation_recovers_exact_pending_provenance(self):
        (self.a / "active-a").write_text("A")
        record = self.plan(self.a)
        self.generation = record["generation"]  # caller dies before finish()
        recovered = state.active(self.repo, self.directory)
        self.assertEqual(recovered, record)
        self.assertFalse((self.directory / "pending.json").exists())

    def test_failed_activation_keeps_previous_active_and_next_task_replans(self):
        (self.a / "failed-a").write_text("not active")
        self.plan(self.a)  # build fails; never selected generation
        (self.b / "own-b").write_text("B")
        record = self.plan(self.b)
        self.assertFalse((Path(record["source"]) / "failed-a").exists())

    def test_main_absorbs_identical_changes_but_conflicting_main_is_blocked(self):
        original = state.layer(self.a)
        (self.a / "active-a").write_text("A")
        incoming = state.layer(self.a)
        self.assertEqual(state.compose(self.repo, incoming["tree"], [incoming]), incoming["tree"])
        (self.b / "active-a").write_text("different integrated change")
        newer_main = state.source_tree(self.b)
        with self.assertRaisesRegex(RuntimeError, "active-a.*integrated main"):
            state.compose(self.repo, newer_main, [incoming])
        self.assertEqual(original["base"], incoming["base"])

    def formatted_fixture(self, integrated='{ value = "same value"; }\n'):
        original = '{value="same value";}\n'
        (self.a / "formatted.nix").write_text(original)
        incoming = state.layer(self.a)
        (self.b / "formatted.nix").write_text(integrated)
        main = state.source_tree(self.b)
        real_output = subprocess.check_output

        def parsed(args, **kwargs):
            if args[0] == "nix-instantiate":
                self.assertEqual(args, ["nix-instantiate", "--parse", "-"])
                blob = kwargs["input"]
                # Model parser output, preserving spaces *inside* Nix strings.
                return b'{ value = "same value"; }' if blob == original.encode() else blob.strip()
            return real_output(args, **kwargs)

        return main, incoming, mock.patch.object(subprocess, "check_output", side_effect=parsed)

    def test_formatted_integration_requires_exact_generation_and_keeps_receipts(self):
        main, incoming, parser = self.formatted_fixture()
        before = (self.directory / "active.json").read_bytes()
        with parser, mock.patch.object(state, "materialize", return_value=self.b) as snapshot, \
                mock.patch.object(state, "evaluated_generation", return_value=self.generation) as evaluate:
            self.assertEqual(state.retire_formatted_integrations(self.repo, main, [incoming], self.generation), [])
            snapshot.assert_called_once_with(self.repo, main, state.compose(self.repo, main, []))
            evaluate.assert_called_once_with(self.b)
        self.assertEqual((self.directory / "active.json").read_bytes(), before)
        self.assertFalse((self.directory / "pending.json").exists())

    def test_formatted_integration_preserves_other_active_layers(self):
        main, incoming, parser = self.formatted_fixture()
        (self.b / "other-active-task").write_text("preserve")
        other = state.layer(self.b)
        with parser, mock.patch.object(state, "materialize", return_value=self.b) as snapshot, \
                mock.patch.object(state, "evaluated_generation", return_value=self.generation):
            self.assertEqual(state.retire_formatted_integrations(self.repo, main, [incoming, other], self.generation), [other])
            self.assertIn("other-active-task", state.entries(self.repo, snapshot.call_args.args[2]))

    def test_formatted_integration_generation_mismatch_blocks_without_receipt_changes(self):
        main, incoming, parser = self.formatted_fixture()
        before = (self.directory / "active.json").read_bytes()
        with parser, mock.patch.object(state, "materialize", return_value=self.b), \
                mock.patch.object(state, "evaluated_generation", return_value="/nix/store/not-installed"):
            with self.assertRaisesRegex(RuntimeError, "exact installed generation"):
                state.retire_formatted_integrations(self.repo, main, [incoming], self.generation)
        self.assertEqual((self.directory / "active.json").read_bytes(), before)
        self.assertFalse((self.directory / "pending.json").exists())

    def test_formatted_integration_never_ignores_string_whitespace_or_non_nix_changes(self):
        for integrated in ('{ value = "same  value"; }\n', '{ value = "different"; }\n'):
            with self.subTest(integrated=integrated):
                main, incoming, parser = self.formatted_fixture(integrated)
                with parser, mock.patch.object(state, "evaluated_generation") as evaluate:
                    self.assertEqual(state.retire_formatted_integrations(self.repo, main, [incoming], self.generation), [incoming])
                    evaluate.assert_not_called()
                with self.assertRaisesRegex(RuntimeError, "formatted.nix.*integrated main"):
                    state.compose(self.repo, main, [incoming])
        main, incoming, parser = self.formatted_fixture()
        (self.a / "README.md").write_text("active task owns this too")
        incoming = state.layer(self.a)
        with parser, mock.patch.object(state, "evaluated_generation") as evaluate:
            self.assertEqual(state.retire_formatted_integrations(self.repo, main, [incoming], self.generation), [incoming])
            evaluate.assert_not_called()

    def test_identical_same_file_edits_coexist_but_deletion_conflicts(self):
        (self.a / "README.md").write_text("identical")
        (self.b / "README.md").write_text("identical")
        main = state.git(self.repo, "rev-parse", "main")
        state.compose(self.repo, main, [state.layer(self.a), state.layer(self.b)])
        (self.b / "README.md").unlink()
        with self.assertRaisesRegex(RuntimeError, "README.md.*feature/task-a.*feature/task-b"):
            state.compose(self.repo, main, [state.layer(self.a), state.layer(self.b)])

    def test_missing_provenance_blocks_and_adoption_cannot_overwrite(self):
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            state.adopt(self.repo, self.a, "feature/task-a", self.directory)
        (self.directory / "active.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "provenance is unknown"):
            self.plan(self.a)
        self.generation = "/nix/store/not-the-candidate"
        with self.assertRaisesRegex(RuntimeError, "does not reproduce"):
            state.adopt(self.repo, self.a, "feature/task-a", self.directory)
        self.assertFalse((self.directory / "active.json").exists())

    def test_integrated_layer_paths_are_retired(self):
        (self.a / "integrated").write_text("A")
        (self.a / "remaining").write_text("still active")
        incoming = state.layer(self.a)
        (self.b / "integrated").write_text("A")
        main = state.source_tree(self.b)
        layers = state.normalize(self.repo, main, [incoming])
        self.assertEqual(len(layers), 1)
        (self.b / "integrated").write_text("newer main revision")
        later = state.source_tree(self.b)
        tree = state.compose(self.repo, later, layers)
        actual = state.entries(self.repo, tree)
        self.assertEqual(actual["integrated"], state.entries(self.repo, later)["integrated"])
        self.assertEqual(actual["remaining"], state.entries(self.repo, incoming["tree"])["remaining"])

    def concurrent_plans(self, conflict=False):
        path_a = "README.md" if conflict else "active-a"
        path_b = "README.md" if conflict else "active-b"
        (self.a / path_a).write_text("task A")
        (self.b / path_b).write_text("task B")
        generation = self.root / "generation"
        generation.write_text(self.generation)
        script = '''
import json, pathlib, sys, time
sys.path.insert(0, sys.argv[1])
import deployment_state as state
repo, directory, generation = map(pathlib.Path, sys.argv[2:5])
owner = sys.argv[5]
state.current_generation = lambda: generation.read_text()
state.evaluated_generation = lambda repo: '/nix/store/fixture-' + state.source_tree(repo)
try:
    with state.lock(directory, owner, timeout=10):
        record = state.plan(repo, directory)
        (directory / (owner + '-planned')).touch()
        if owner == 'a':
            while not (directory / 'release').exists(): time.sleep(.02)
        state.preactivate(repo, directory)
        generation.write_text(record['generation'])
        state.finish(repo, directory)
except RuntimeError as error:
    print(error, file=sys.stderr)
    sys.exit(1)
'''
        args = [sys.executable, "-c", script, str(ROOT / ".mise/scripts")]
        a = subprocess.Popen(args + [str(self.a), str(self.directory), str(generation), "a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        b = None
        try:
            import time
            deadline = time.monotonic() + 10
            while not (self.directory / "a-planned").exists():
                self.assertIsNone(a.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.02)
            b = subprocess.Popen(args + [str(self.b), str(self.directory), str(generation), "b"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(.3)
            self.assertFalse((self.directory / "b-planned").exists())
            (self.directory / "release").touch()
            out_a, err_a = a.communicate(timeout=15)
            out_b, err_b = b.communicate(timeout=15)
            self.assertEqual(a.returncode, 0, err_a)
            self.assertIn("Waiting for active deployment", out_b)
            record = json.loads((self.directory / "active.json").read_text())
            if conflict:
                self.assertEqual(b.returncode, 1, err_b)
                self.assertIn("README.md", err_b)
                self.assertIn("feature/task-a", err_b)
                self.assertIn("feature/task-b", err_b)
                self.assertEqual((Path(record["source"]) / "README.md").read_text(), "task A")
            else:
                self.assertEqual(b.returncode, 0, err_b)
                self.assertEqual((Path(record["source"]) / "active-a").read_text(), "task A")
                self.assertEqual((Path(record["source"]) / "active-b").read_text(), "task B")
        finally:
            for child in (a, b):
                if child is not None:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=5)

    def test_simultaneous_real_worktrees_replan_after_first_unintegrated_activation(self):
        self.concurrent_plans()

    def test_simultaneous_real_worktrees_stop_on_actual_overlap(self):
        self.concurrent_plans(conflict=True)

    def test_generation_guard_and_cancelled_plan_block_activation(self):
        (self.a / "active-a").write_text("A")
        self.plan(self.a)
        self.generation = "/nix/store/unrecorded-other-task"
        with self.assertRaisesRegex(RuntimeError, "changed after deployment planning"):
            state.preactivate(self.repo, self.directory)
        with mock.patch.object(state, "CANCELLED", 15):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.plan(self.b)

    def test_profiles_unchanged(self):
        before = {key: os.environ.get(key) for key in ("PI_CODING_AGENT_DIR", "CLAUDE_CONFIG_DIR")}
        self.plan(self.a)
        self.assertEqual(before, {key: os.environ.get(key) for key in before})


class ApplyRouting(unittest.TestCase):
    def test_installed_entry_preserves_inherited_context_without_reentering_mise(self):
        for platform in ("darwin", "linux"):
            with self.subTest(platform=platform), \
                 mock.patch.object(sys, "argv", ["coordinator", "apply", "/verified/task", "--switch-only"]), \
                 mock.patch.object(sys, "platform", platform), \
                 mock.patch.dict(os.environ, PI_CODING_AGENT_DIR="/inherited/work-pi",
                                 CLAUDE_CONFIG_DIR="/inherited/work-claude", MISE_CONTEXT="inherited"), \
                 mock.patch.object(state.subprocess, "run") as child:
                child.return_value.returncode = 0
                self.assertEqual(state.main(), 0)
                args, kwargs = child.call_args
                self.assertNotIn("mise", args[0])
                self.assertEqual(kwargs["cwd"], Path("/verified/task"))
                self.assertEqual(kwargs["env"]["PI_CODING_AGENT_DIR"], "/inherited/work-pi")
                self.assertEqual(kwargs["env"]["CLAUDE_CONFIG_DIR"], "/inherited/work-claude")
                self.assertEqual(kwargs["env"]["MISE_CONTEXT"], "inherited")


class Serialization(unittest.TestCase):
    def test_parallel_tasks_wait_re_read_and_kernel_releases_dead_owner(self):
        with tempfile.TemporaryDirectory(prefix="deployment-lock-test-") as directory:
            root = Path(directory)
            script = '''
import pathlib, sys, time
sys.path.insert(0, sys.argv[1])
import deployment_state as state
root, owner = pathlib.Path(sys.argv[2]), sys.argv[3]
with state.lock(root, owner, timeout=5):
    previous = (root / 'active').read_text() if (root / 'active').exists() else ''
    (root / (owner + '-entered')).touch()
    if owner == 'a':
        while not (root / 'release').exists(): time.sleep(.02)
    (root / 'active').write_text(previous + owner)
'''
            args = [sys.executable, "-c", script, str(ROOT / ".mise/scripts"), str(root)]
            a = subprocess.Popen(args + ["a"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            b = None
            try:
                import time
                deadline = time.monotonic() + 5
                while not (root / "a-entered").exists():
                    self.assertIsNone(a.poll())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.02)
                b = subprocess.Popen(args + ["b"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                time.sleep(.3)
                self.assertFalse((root / "b-entered").exists())
                (root / "release").touch()
                self.assertEqual(a.wait(timeout=5), 0)
                self.assertEqual(b.wait(timeout=5), 0)
                self.assertEqual((root / "active").read_text(), "ab")
                self.assertIn("Waiting for active deployment", b.stdout.read())
                # Stale PID metadata is not a lock and does not need deleting.
                (root / "lock").write_text('{"pid": 99999999, "owner": "dead"}')
                with state.lock(root, "new-owner", timeout=0):
                    with self.assertRaisesRegex(RuntimeError, "busy.*new-owner"):
                        with state.lock(root, "competing-owner", timeout=0):
                            self.fail("overlapping lock acquired")
            finally:
                for child in (a, b):
                    if child is not None:
                        if child.poll() is None:
                            child.kill()
                        child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
