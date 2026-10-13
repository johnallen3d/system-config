#!/usr/bin/env python3
"""#781 source relocation tests: synthetic repositories/evidence, no live actions."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "modules/home-manager/hermes-native"
spec = importlib.util.spec_from_file_location("source_test_runtime", ASSETS / "production-runtime.py")
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return sha(path.read_bytes())


class EngineeringSource(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hermes-source-781-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.repo = self.home / "dev/src/system-config"
        self.repo.mkdir(parents=True)
        self.git = shutil.which("git")
        self.assertIsNotNone(self.git)
        self.git_env = {"HOME": str(self.home), "PATH": os.environ["PATH"],
                        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
        self.run_git(self.repo, "init", "-q", "--initial-branch=main")
        # Git permits an unborn linked worktree; no commits or actual repos touched.
        self.task = self.repo / ".worktrees/source-relocation"
        self.run_git(self.repo, "worktree", "add", "-q", "--orphan", "-b",
                     "feature/source-relocation", str(self.task))
        self.meta = {"vault": str(self.home / "notes"),
                     "environment": {"PATH": os.environ["PATH"]}}

    def run_git(self, root, *args):
        return subprocess.run([self.git, "-C", str(root), *args], env=self.git_env,
                              capture_output=True, text=True, check=True)

    def test_primary_and_linked_task_worktree_are_verified(self):
        for source in (self.repo, self.task):
            self.assertEqual(runtime.engineering_source(self.meta, str(source)), source)

    def test_missing_relative_and_parent_traversal_binding_are_refused(self):
        for source in (None, "", "system-config", str(self.task / ".." / "source-relocation")):
            with self.subTest(source=source), self.assertRaises(ValueError):
                runtime.engineering_source(self.meta, source)

    def test_symlink_alias_is_refused(self):
        alias = self.repo / ".worktrees/compatibility-alias"
        alias.symlink_to(self.task, target_is_directory=True)
        with self.assertRaises(ValueError):
            runtime.engineering_source(self.meta, str(alias))

    def test_snapshot_inside_worktree_directory_is_refused(self):
        snapshot = self.repo / ".worktrees/copied-snapshot"
        snapshot.mkdir()
        # Without --show-toplevel verification Git could mistake its parent for it.
        with self.assertRaises(ValueError):
            runtime.engineering_source(self.meta, str(snapshot))

    def test_copied_git_pointer_is_not_a_registered_worktree(self):
        snapshot = self.repo / ".worktrees/fake-linked-worktree"
        snapshot.mkdir()
        shutil.copyfile(self.task / ".git", snapshot / ".git")
        with self.assertRaises(ValueError):
            runtime.engineering_source(self.meta, str(snapshot))

    def test_independent_nested_repository_is_refused(self):
        other = self.repo / ".worktrees/independent-repository"
        other.mkdir()
        self.run_git(other, "init", "-q")
        with self.assertRaises(ValueError):
            runtime.engineering_source(self.meta, str(other))

    def test_foreign_checkout_and_missing_git_are_refused(self):
        other = self.home / "other-system-config"
        other.mkdir()
        self.run_git(other, "init", "-q")
        with self.assertRaises(ValueError):
            runtime.engineering_source(self.meta, str(other))
        with self.assertRaises(ValueError):
            runtime.engineering_source(dict(self.meta, environment={"PATH": ""}), str(self.task))

    def test_inherited_git_overrides_cannot_redirect_the_check(self):
        with patch.dict(os.environ, {"GIT_DIR": str(self.home / "unknown"),
                                    "GIT_WORK_TREE": str(self.home / "unknown")}):
            self.assertEqual(runtime.engineering_source(self.meta, str(self.task)), self.task)

    def evidence(self):
        state = self.home / "state"
        control = state / "controller"
        control.mkdir(parents=True)
        generation = self.home / "immutable-generation"
        generation.mkdir()
        asset = self.task / "modules/home-manager/hermes-native/fixture.py"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"# Exact synthetic approved fixture\n")
        lock = self.task / "flake.lock"
        lock.write_bytes(b'{"syntheticLock":1}\n')
        task = Path(self.meta["vault"]) / ".mise/tasks/read-only"
        task.parent.mkdir(parents=True)
        task.write_bytes(b"echo synthetic\n")
        code = {"fixture.py": sha(asset.read_bytes()), "@fixture": "synthetic-identity"}
        providers = {"reports": {"get-calendar": {"observedAt": time.time()}}}
        provider_sha = private_json(control / "engineering-providers.json", providers)
        component_sha = private_json(control / "engineering-components.json", {"synthetic": True})
        task_code = {".mise/tasks/read-only": sha(task.read_bytes())}
        private_json(control / "task-code.json", {
            "kind": "REVIEWED_USER_OWNED_VAULT_TASK_CODE",
            "namespace": runtime.t.NAMESPACE, "files": task_code})
        receipt = {"kind": "HERMES763_ACTUAL_PRESTOP_ENGINEERING",
                   "namespace": runtime.t.NAMESPACE, "revision": runtime.p.stage.REVISION,
                   "productionReady": True, "installedGeneration": str(generation), "code": code,
                   "recordedAt": time.time(), "providerEvidenceSha256": provider_sha,
                   "componentEvidenceSha256": component_sha, "taskCode": task_code,
                   "sourceRoot": str(self.task),
                   "sourceHashes": {"fixture.py": code["fixture.py"], "@flake.lock": sha(lock.read_bytes())}}
        for key in ("runtimeGuard", "coldImport", "reverseRecovery", "writerGate",
                    "nasRedeployGuard", "sourceProfileCAS", "syncthingConvergence"):
            receipt[key] = "PASS"
        private_json(control / "engineering.json", receipt)
        meta = dict(self.meta, paths={"state": str(state)})
        return meta, receipt, generation, code, asset, lock, task

    def receipt_check(self, meta, generation, code):
        def path(value):
            if str(value) == "/home/johna/.local/state/nix/profiles/home-manager":
                return generation
            return Path(value)
        # Only synthetic stopped-owner/installed-generation preconditions are mocked;
        # the actual receipt binding and source/lock/task CAS checks execute below.
        with patch.object(runtime, "Path", side_effect=path), \
                patch.object(runtime, "check", return_value=None), \
                patch.object(runtime, "engineering_identity", return_value=code):
            return runtime.engineering_evidence(meta)

    def test_relocated_receipt_preserves_all_exact_cas_checks_without_writes(self):
        meta, receipt, generation, code, asset, lock, task = self.evidence()
        before = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(self.receipt_check(meta, generation, code), receipt)
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()})
        for target in (asset, lock, task):
            original = target.read_bytes()
            target.write_bytes(original + b"DRIFT\n")
            with self.subTest(target=target.name), self.assertRaises(ValueError):
                self.receipt_check(meta, generation, code)
            target.write_bytes(original)

    def test_historical_receipt_without_source_binding_is_not_rewritten(self):
        meta, receipt, generation, code, *_ = self.evidence()
        del receipt["sourceRoot"]
        path = Path(meta["paths"]["state"]) / "controller/engineering.json"
        private_json(path, receipt)
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.receipt_check(meta, generation, code)
        self.assertEqual(path.read_bytes(), before)

    def test_all_three_engineering_paths_use_explicit_source_binding(self):
        source = (ASSETS / "production-runtime.py").read_text()
        tree = ast.parse(source)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for name in ("engineering_ready", "engineering_evidence", "final_gate_evidence"):
            calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == "engineering_source"]
            self.assertEqual(len(calls), 1, name)
            self.assertIn("sourceRoot", ast.unparse(calls[0]), name)
        self.assertNotIn("system-config-amfaro", source)
        self.assertNotIn("system-config-amfaro", (ASSETS.parent / "hermes-packaging-adopt.py").read_text())


if __name__ == "__main__":
    unittest.main()
