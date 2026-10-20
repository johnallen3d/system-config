#!/usr/bin/env python3
"""Offline routing/concurrency and real-Git transport checks; never deploy hosts."""

import base64
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".mise/scripts"))
loader = importlib.machinery.SourceFileLoader("omarchy_deploy", str(ROOT / ".mise/scripts/update-system-omarchy"))
spec = importlib.util.spec_from_loader(loader.name, loader)
worker = importlib.util.module_from_spec(spec)
loader.exec_module(worker)


class Routing(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="update-system-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "checkout with spaces"
        (self.repo / ".mise/tasks").mkdir(parents=True)
        (self.repo / ".mise/scripts").mkdir()
        self.task = self.repo / ".mise/tasks/update-system"
        shutil.copyfile(ROOT / ".mise/tasks/update-system", self.task)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "events.jsonl"
        mock = self.bin / "mock"
        mock.write_text(f"#!{shutil.which('python3')}\n" + '''
import json, os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['EVENTS'], 'a') as output:
    output.write(json.dumps([name, args]) + '\\n')
if name == 'uname':
    print(os.environ.get('PLATFORM', 'Darwin'))
elif name == 'sudo':
    sys.exit(int(os.environ.get('SUDO_RC', '0')))
elif name == 'mise':
    if '--update-only' in args:
        sys.exit(int(os.environ.get('UPDATE_RC', '0')))
    if args[:2] == ['run', 'nix-rebuild']:
        root = pathlib.Path(os.environ['MARKERS'])
        (root / 'mac').touch()
        if os.environ.get('REQUIRE_PARALLEL'):
            for i in range(100):
                if (root / 'omarchy').exists(): break
                time.sleep(.02)
            else: sys.exit(98)
        sys.exit(int(os.environ.get('MAC_RC', '0')))
''')
        mock.chmod(0o700)
        for name in ("uname", "sudo", "mise"):
            (self.bin / name).symlink_to(mock)
        (self.repo / ".mise/scripts/update-system-omarchy").write_text('''
import json, os, pathlib, sys, time
mode = sys.argv[1]
with open(os.environ['EVENTS'], 'a') as output:
    output.write(json.dumps(['worker', [mode]]) + '\\n')
if mode == 'deploy':
    root = pathlib.Path(os.environ['MARKERS'])
    (root / 'omarchy').touch()
    if os.environ.get('REQUIRE_PARALLEL'):
        for i in range(100):
            if (root / 'mac').exists(): break
            time.sleep(.02)
        else: sys.exit(97)
    sys.exit(int(os.environ.get('OMARCHY_RC', '0')))
sys.exit(int(os.environ.get(mode.upper() + '_RC', '0')))
''')
        (self.repo / ".mise/scripts/deployment_state.py").write_text('''
import os, pathlib, subprocess, sys
mode, repo = sys.argv[1:3]
if mode == "run":
    sys.exit(subprocess.run(sys.argv[3:], env=dict(os.environ, SYSTEM_CONFIG_COORDINATED=repo)).returncode)
if mode == "plan":
    pathlib.Path(sys.argv[3]).write_text(repo)
''')
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("usage_", "SYSTEM_CONFIG_"))}
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", EVENTS=str(self.log), MARKERS=str(self.root))

    def invoke(self, **variables):
        return subprocess.run(["bash", str(self.task)], env=dict(self.env, **variables),
                              cwd=self.root, capture_output=True, text=True, timeout=15)

    def events(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_parallel_default_updates_inputs_once(self):
        result = self.invoke(REQUIRE_PARALLEL="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events()
        self.assertEqual([e for e in events if e[0] == "mise"], [
            ["mise", ["run", "nix-rebuild", "--update-only"]],
            ["mise", ["run", "nix-rebuild", "--switch-only"]]])
        checks = [e[1] for e in events if e[0] == "sudo"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0][:4], ["-n", "-l", "--", "/run/current-system/sw/bin/darwin-rebuild"])
        self.assertNotIn("-v", checks[0])
        self.assertIn(["worker", ["deploy"]], events)
        self.assertEqual(events[-1], ["worker", ["check"]])
        self.assertIn("[Mac] SUCCESS", result.stdout)
        self.assertIn("[Omarchy] SUCCESS", result.stdout)

    def test_switch_only_does_not_update_inputs(self):
        result = self.invoke(usage_switch_only="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(["mise", ["run", "nix-rebuild", "--update-only"]], self.events())

    def test_picker_only_resolves_before_both_builds(self):
        result = self.invoke(usage_picker_only="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(next(e for e in self.events() if e[0] == "mise"),
                         ["mise", ["run", "nix-rebuild", "--update-only", "--picker-only"]])

    def test_local_only_explicitly_skips_remote_and_forwards_refresh_scope(self):
        result = self.invoke(usage_switch_only="true", usage_local_only="true", usage_harness_refresh="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(e[0] in ("worker", "sudo") for e in self.events()))
        self.assertEqual(self.events()[-1], ["mise", ["run", "harness-refresh", "--local-only"]])
        self.assertIn("Omarchy explicitly skipped", result.stdout)

    def test_either_host_failure_is_partial_and_skips_harness_refresh(self):
        for failure in ("MAC_RC", "OMARCHY_RC", "CHECK_RC"):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                result = self.invoke(usage_switch_only="true", usage_harness_refresh="true", **{failure: "7"})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("partial", result.stderr)
                self.assertIn(["worker", ["deploy"]], self.events())
                self.assertIn(["mise", ["run", "nix-rebuild", "--switch-only"]], self.events())
                self.assertFalse(any("harness-refresh" in e[1] for e in self.events()))

    def test_refresh_is_after_both_deployments(self):
        result = self.invoke(usage_switch_only="true", usage_harness_refresh="true", REQUIRE_PARALLEL="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events()[-1], ["mise", ["run", "harness-refresh"]])

    def test_update_failure_prevents_both_deployments(self):
        result = self.invoke(UPDATE_RC="6")
        self.assertEqual(result.returncode, 6)
        self.assertFalse(any(e[0] in ("worker", "sudo") for e in self.events()))

    def test_sudo_failure_prevents_background_deployments(self):
        result = self.invoke(usage_switch_only="true", SUDO_RC="3")
        self.assertEqual(result.returncode, 3)
        self.assertNotIn(["worker", ["deploy"]], self.events())
        self.assertFalse(any(e[0] == "mise" for e in self.events()))

    def test_installed_tooling_never_executes_older_task_rebuild(self):
        tools = self.root / "installed tools"
        shutil.copytree(self.repo / ".mise", tools / ".mise")
        current = tools / ".mise/tasks/nix-rebuild"
        current.write_text('''#!/usr/bin/env bash
set -eu
[[ "$SYSTEM_CONFIG_TASK_ROOT" == "$EXPECTED_TASK" ]]
[[ "$usage_switch_only" == true ]]
printf "installed-rebuild\\n"
[[ -n "$PI_CODING_AGENT_DIR" && -n "$CLAUDE_CONFIG_DIR" ]]
''')
        (self.repo / ".mise/tasks/nix-rebuild").write_text("exit 97\n")
        result = self.invoke(usage_switch_only="true", usage_local_only="true",
                             SYSTEM_CONFIG_TOOL_ROOT=str(tools), SYSTEM_CONFIG_TASK_ROOT=str(self.repo),
                             EXPECTED_TASK=str(self.repo), PI_CODING_AGENT_DIR="/inherited/pi",
                             CLAUDE_CONFIG_DIR="/inherited/claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installed-rebuild", result.stdout)
        self.assertFalse(any(e[0] == "mise" and "nix-rebuild" in e[1] for e in self.events()))

    def test_invalid_flags_prevent_side_effects(self):
        result = self.invoke(usage_switch_only="true", usage_picker_only="true")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.events(), [["uname", ["-s"]]])


class Transport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="update-system-git-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / "local source"
        self.remote = self.root / "remote source"
        # Existing history supplies fixtures: no commits in the user's repository
        # (or synthetic commits at all) are needed for these tests.
        for repo in (self.local, self.remote):
            subprocess.run(["git", "clone", "--quiet", "--shared", "--branch", "main", str(ROOT), str(repo)], check=True)
        worker.git(self.local, "config", "color.ui", "always")
        worker.git(self.local, "config", "diff.external", "false")
        self.payload = self.root / "payload"
        self.payload.mkdir()

    def prepare(self):
        worker.prepare(self.local, self.payload)
        return json.loads((self.payload / "manifest.json").read_text())

    def test_binary_new_deleted_symlink_and_modes_without_staging(self):
        before = (self.local / ".git/index").read_bytes()
        (self.local / "new binary").write_bytes(b"\x00\xff\x01source")
        (self.local / "source-link").symlink_to("new binary")
        (self.local / "README.md").unlink()
        script = self.local / ".mise/tasks/update-system"
        script.chmod(0o644)
        (self.local / ".gitignore").write_text((self.local / ".gitignore").read_text() + "\nignored-secret\n")
        (self.local / "ignored-secret").write_text("must not cross SSH")
        manifest = self.prepare()
        self.assertEqual((self.local / ".git/index").read_bytes(), before)
        self.assertNotIn(b"must not cross SSH", (self.payload / "source.patch").read_bytes())
        task, tree = worker.receive(self.payload, self.remote)
        self.assertEqual(tree, manifest["tree"])
        self.assertEqual(worker.source_tree(task), worker.source_tree(self.local))
        self.assertEqual((task / "new binary").read_bytes(), b"\x00\xff\x01source")
        self.assertTrue((task / "source-link").is_symlink())
        self.assertFalse((task / "ignored-secret").exists())
        self.assertFalse((task / "README.md").exists())
        self.assertEqual((task / ".mise/tasks/update-system").stat().st_mode & 0o777, 0o644)
        self.assertEqual(worker.git(self.remote, "status", "--porcelain"), "")
        self.assertEqual(worker.receive(self.payload, self.remote)[0], task)

    def test_payload_is_bounded_and_never_serializes_inherited_profiles(self):
        self.prepare()
        with mock.patch.object(worker.subprocess, "run") as transport:
            worker.deploy(self.payload)
        args, kwargs = transport.call_args
        self.assertEqual(args[0], worker.SSH)
        script = kwargs["input"]
        payload = script.split("\nUPDATE_SYSTEM_PAYLOAD\n")[0].split("\n")[-1]
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(payload)), mode="r:gz") as archive:
            self.assertEqual(set(archive.getnames()), {"main.bundle", "source.patch", "manifest.json", "worker.py", "deployment_state.py"})
        self.assertNotIn(os.environ.get("PI_CODING_AGENT_DIR", "/inherited-profile"), script)
        self.assertNotIn(os.environ.get("CLAUDE_CONFIG_DIR", "/inherited-claude"), script)
        self.assertIn('python3 "$directory/worker.py" remote "$directory"', script)

    def test_main_advance_after_mac_plan_requires_retry_before_deployments(self):
        planned = self.local / ".worktrees/old-planned-source"
        worker.git(self.local, "worktree", "add", "--detach", str(planned), "main^")
        with self.assertRaisesRegex(RuntimeError, "Main advanced after Mac planning"):
            worker.prepare(self.local, self.payload, planned)
        self.assertFalse((self.payload / "manifest.json").exists())

    def test_remote_main_fast_forwards_integrated_history(self):
        old = worker.git(self.remote, "rev-parse", "main^")
        worker.git(self.remote, "reset", "--hard", old)
        manifest = self.prepare()
        task, _ = worker.receive(self.payload, self.remote)
        self.assertEqual(worker.git(self.remote, "rev-parse", "main"), manifest["main"])
        self.assertEqual(worker.git(task, "rev-parse", "HEAD"), manifest["main"])

    def test_dirty_primary_is_preserved(self):
        marker = self.remote / "unrelated.txt"
        marker.write_text("leave me alone")
        self.prepare()
        with self.assertRaisesRegex(RuntimeError, "primary checkout has changes"):
            worker.receive(self.payload, self.remote)
        self.assertEqual(marker.read_text(), "leave me alone")

    def test_remote_main_ahead_is_not_replaced(self):
        original = worker.git(self.remote, "rev-parse", "main")
        worker.git(self.local, "reset", "--hard", "main^")
        self.prepare()
        with self.assertRaisesRegex(RuntimeError, "ahead or diverged"):
            worker.receive(self.payload, self.remote)
        self.assertEqual(worker.git(self.remote, "rev-parse", "main"), original)

    def test_modified_deployment_worktree_is_not_reset(self):
        self.prepare()
        task, _ = worker.receive(self.payload, self.remote)
        marker = task / "unrelated.txt"
        marker.write_text("keep this")
        with self.assertRaisesRegex(RuntimeError, "refusing to overwrite"):
            worker.receive(self.payload, self.remote)
        self.assertEqual(marker.read_text(), "keep this")

    def test_ignored_files_in_deployment_are_not_used_or_removed(self):
        self.prepare()
        task, _ = worker.receive(self.payload, self.remote)
        marker = task / ".fizzy.yaml"
        marker.write_text("preserve ignored user config")
        with self.assertRaisesRegex(RuntimeError, "Unexpected ignored files"):
            worker.receive(self.payload, self.remote)
        self.assertEqual(marker.read_text(), "preserve ignored user config")

    def test_unrelated_linked_worktree_is_untouched(self):
        other = self.remote / ".worktrees/unrelated"
        worker.git(self.remote, "worktree", "add", "-b", "feature/unrelated", str(other), "main")
        (other / "my-file").write_text("unrelated work")
        self.prepare()
        worker.receive(self.payload, self.remote)
        self.assertEqual((other / "my-file").read_text(), "unrelated work")


if __name__ == "__main__":
    unittest.main(verbosity=2)
