#!/usr/bin/env python3

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "modules/home-manager/agent-projects/personal-wrap.md"
MERGE, REMOVE = re.findall(r"```bash\n(.*?)\n\s*```", LIFECYCLE.read_text(), re.S)
REBASE = re.search(r'Use `(git .*? rebase .*?)`\.', LIFECYCLE.read_text()).group(1)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="personal worktree ")
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name).resolve()
        self.primary = self.parent / "primary repo"
        self.task = self.primary / ".worktrees/test-task"
        self.branch = "feature/test-task"
        self.env = dict(os.environ, HOME=str(self.parent), XDG_CONFIG_HOME=str(self.parent / "config"),
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                        GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                        GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid")
        self.git(self.parent, "init", "--quiet", "--initial-branch=main", str(self.primary))
        (self.primary / ".gitignore").write_text(".worktrees/\nignored-artifact\n")
        (self.primary / "tracked").write_text("base\n")
        self.git(self.primary, "add", ".gitignore", "tracked")
        self.git(self.primary, "commit", "--quiet", "-m", "test: initialize fixture")
        self.base = self.git(self.primary, "rev-parse", "main")
        self.git(self.primary, "worktree", "add", "--quiet", "-b", self.branch, str(self.task), "main")
        self.env.update(repo_root=str(self.primary), task_path=str(self.task), task_branch=self.branch)
        self.commit(self.task, "task", "task change\n")
        self.tip = self.git(self.task, "rev-parse", "HEAD")

    def git(self, cwd, *args):
        return subprocess.check_output(["git", "-C", str(cwd), *args], env=self.env,
                                       text=True, stderr=subprocess.PIPE).strip()

    def commit(self, cwd, name, content):
        (cwd / name).write_text(content)
        self.git(cwd, "add", name)
        self.git(cwd, "commit", "--quiet", "-m", "test: update fixture")

    def run_block(self, block, cwd=None, **variables):
        return subprocess.run(["bash", "-c", block], cwd=cwd or self.primary,
                              env=dict(self.env, **variables), capture_output=True, text=True)

    def assert_retained(self):
        self.assertTrue(self.task.is_dir())
        self.assertEqual(self.git(self.task, "branch", "--show-current"), self.branch)
        self.assertIn(str(self.task), self.git(self.primary, "worktree", "list", "--porcelain"))

    def test_fast_forward_and_targeted_cleanup(self):
        other = self.primary / ".worktrees/other-task"
        self.git(self.primary, "worktree", "add", "--quiet", "-b", "feature/other-task", str(other), "main")
        merge = self.run_block(MERGE)
        self.assertEqual(merge.returncode, 0, merge.stderr)
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), self.tip)
        self.assertEqual(self.git(self.task, "rev-parse", "HEAD"), self.tip)
        remove = self.run_block(REMOVE)
        self.assertEqual(remove.returncode, 0, remove.stderr)
        self.assertFalse(self.task.exists())
        self.assertNotIn(str(self.task), self.git(self.primary, "worktree", "list", "--porcelain"))
        self.assertNotIn(self.branch, self.git(self.primary, "branch", "--format=%(refname:short)"))
        self.assertTrue(other.is_dir())
        self.assertEqual(self.git(other, "rev-parse", "HEAD"), self.base)
        self.assertEqual(self.git(self.primary, "status", "--porcelain"), "")

    def test_already_integrated_task_needs_no_commit(self):
        self.git(self.primary, "merge", "--ff-only", self.branch)
        merge = self.run_block(MERGE)
        self.assertEqual(merge.returncode, 0, merge.stderr)
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), self.tip)
        remove = self.run_block(REMOVE)
        self.assertEqual(remove.returncode, 0, remove.stderr)

    def test_integrated_task_with_main_ahead(self):
        self.git(self.primary, "merge", "--ff-only", self.branch)
        self.commit(self.primary, "later-main-change", "main advanced after integration\n")
        main_tip = self.git(self.primary, "rev-parse", "main")
        merge = self.run_block(MERGE)
        self.assertEqual(merge.returncode, 0, merge.stderr)
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), main_tip)
        remove = self.run_block(REMOVE)
        self.assertEqual(remove.returncode, 0, remove.stderr)
        self.assertFalse(self.task.exists())

    def test_divergent_main_preserves_both_tips(self):
        self.commit(self.primary, "main-change", "independent main change\n")
        main_tip = self.git(self.primary, "rev-parse", "main")
        self.assertNotEqual(self.run_block(MERGE).returncode, 0)
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), main_tip)
        self.assertEqual(self.git(self.task, "rev-parse", "HEAD"), self.tip)
        self.assertNotEqual(self.run_block(REMOVE).returncode, 0)
        self.assert_retained()

    def test_reviewed_unpublished_task_rebases_after_main_advances(self):
        before = self.git(self.task, "show", "-s", "--format=%an <%ae>%n%aI%n%B")
        self.commit(self.primary, "main-change", "independent main change\n")
        main_tip = self.git(self.primary, "rev-parse", "main")
        # This disposable fixture has known task ownership/non-publication.
        result = self.run_block(REBASE, main_tip=main_tip, base=self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), main_tip)
        self.assertNotEqual(self.git(self.task, "rev-parse", "HEAD"), self.tip)
        self.assertEqual(self.git(self.task, "show", "-s", "--format=%an <%ae>%n%aI%n%B"), before)
        self.assertEqual(self.run_block(MERGE).returncode, 0)
        self.assertEqual(self.run_block(REMOVE).returncode, 0)

    def test_rebase_conflict_and_signing_failure_preserve_task(self):
        self.commit(self.primary, "task", "conflicting main content\n")
        main_tip = self.git(self.primary, "rev-parse", "main")
        result = self.run_block(REBASE, main_tip=main_tip, base=self.base)
        self.assertNotEqual(result.returncode, 0)
        git_dir = Path(self.git(self.task, "rev-parse", "--absolute-git-dir"))
        self.assertTrue((git_dir / "rebase-merge").is_dir())
        self.assertNotEqual(self.run_block(MERGE).returncode, 0)
        self.assertNotEqual(self.run_block(REMOVE).returncode, 0)
        # Explicit fixture teardown only; the lifecycle leaves failures intact.
        self.git(self.task, "rebase", "--abort")
        self.git(self.task, "config", "commit.gpgsign", "true")
        self.git(self.task, "config", "gpg.program", "/nonexistent-fixture-signer")
        self.git(self.task, "config", "rerere.enabled", "false")
        # Rebase onto the base avoids conflict and exercises required signing.
        result = self.run_block(REBASE.replace(" rebase ", " rebase --force-rebase "),
                                main_tip=self.base, base=self.base)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((git_dir / "rebase-merge").is_dir())
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), main_tip)
        self.assertTrue(self.task.is_dir())
        self.assertEqual(self.git(self.primary, "rev-parse", self.branch), self.tip)

    def test_guarded_rebase_instruction_boundaries(self):
        policy = " ".join(LIFECYCLE.read_text().split())
        for clause in ("only this task's own unpublished local commits", "not proof",
                       "Uncertain ownership/publication", "Do not fetch or push",
                       "required signatures on rewritten commits", "never bypass signing or hooks",
                       "no existing Git operation", "unchanged tips immediately",
                       "No automatic resolution, abort, skip", "rerun relevant gates",
                       "not an unconditional rebuild/redeploy", "validated main/task tips"):
            self.assertIn(clause, policy)

    def test_dirty_primary_and_task_block_merge(self):
        for cwd in (self.primary, self.task):
            for name in ("tracked", "untracked"):
                with self.subTest(cwd=cwd, name=name):
                    path = cwd / name
                    original = path.read_text() if path.exists() else None
                    path.write_text("unfinished work\n")
                    self.assertNotEqual(self.run_block(MERGE).returncode, 0)
                    self.assertEqual(self.git(self.primary, "rev-parse", "main"), self.base)
                    self.assert_retained()
                    if original is None:
                        path.unlink()
                    else:
                        path.write_text(original)

    def test_ignored_primary_file_blocks_integration(self):
        primary_file = self.primary / "ignored-artifact"
        primary_file.write_text("local content must survive\n")
        (self.task / "ignored-artifact").write_text("tracked task content\n")
        self.git(self.task, "add", "--force", "ignored-artifact")
        self.git(self.task, "commit", "--quiet", "-m", "test: track ignored path")
        self.assertNotEqual(self.run_block(MERGE).returncode, 0)
        self.assertEqual(primary_file.read_text(), "local content must survive\n")
        self.assertEqual(self.git(self.primary, "rev-parse", "main"), self.base)
        self.assert_retained()

    def test_cleanup_preserves_untracked_and_ignored_files(self):
        self.git(self.primary, "merge", "--ff-only", self.branch)
        for name in ("tracked", "untracked", "ignored-artifact"):
            with self.subTest(name=name):
                path = self.task / name
                original = path.read_text() if path.exists() else None
                path.write_text("must survive\n")
                self.assertNotEqual(self.run_block(REMOVE).returncode, 0)
                self.assertEqual(path.read_text(), "must survive\n")
                self.assert_retained()
                if original is None:
                    path.unlink()
                else:
                    path.write_text(original)

    def test_cleanup_requires_primary_cwd_and_integration(self):
        self.assertNotEqual(self.run_block(REMOVE).returncode, 0)
        self.assert_retained()
        self.git(self.primary, "merge", "--ff-only", self.branch)
        for cwd in (self.task, self.parent):
            with self.subTest(cwd=cwd):
                self.assertNotEqual(self.run_block(REMOVE, cwd=cwd).returncode, 0)
                self.assert_retained()

    def test_directory_scoped_task_commands_preserve_primary_shell(self):
        result = self.run_block(
            'git -C "$task_path" rev-parse --show-toplevel\n'
            '(cd "$task_path" && pwd -P)\n'
            'pwd -P'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         [str(self.task), str(self.task), str(self.primary)])

    def test_persistent_shell_drift_can_recover_before_cleanup(self):
        self.git(self.primary, "merge", "--ff-only", self.branch)
        # Model a persistent Bash session with separate commands. This proves
        # shell behavior, not Claude harness metadata or session-start evidence.
        with subprocess.Popen(["bash"], cwd=self.primary, env=self.env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as shell:
            def command(text):
                shell.stdin.write(text + "\n")
                shell.stdin.flush()

            command('cd "$task_path"')
            command('pwd -P')
            self.assertEqual(shell.stdout.readline().strip(), str(self.task))
            command('cd "$repo_root"')  # Standalone recovery, not a guard override.
            command('pwd -P')  # Fresh subsequent command verifies persisted cwd.
            self.assertEqual(shell.stdout.readline().strip(), str(self.primary))
            command(REMOVE)
            stdout, stderr = shell.communicate(timeout=15)
        self.assertEqual(shell.returncode, 0, stdout + stderr)
        self.assertFalse(self.task.exists())
        self.assertNotIn(self.branch, self.git(self.primary, "branch", "--format=%(refname:short)"))

    def test_cwd_recovery_policy_preserves_launch_and_harness_guards(self):
        policy = " ".join(LIFECYCLE.read_text().split())
        for clause in (
            "harness and verified startup cwd", "Per global cwd rules",
            "only Claude shell drift from a verified primary-root start permits standalone",
            '`cd "$repo_root"`', "verify harness cwd AND a separate plain `pwd -P`",
            "in a fresh tool call", "no inline `cd`/cwd override",
            "Actual worktree starts/unknown evidence require verified primary-root resume/relaunch",
            "retain task if either cwd is unverified",
            "Shell-only proof/`process.chdir`/context mutation are invalid",
        ):
            self.assertIn(clause, policy)
        self.assertNotIn('cd "$repo_root"', REMOVE)
        self.assertIn('test "$(pwd -P)" = "$repo_root"', REMOVE)

    def test_wrong_branch_missing_main_and_locked_worktree(self):
        self.git(self.primary, "switch", "--quiet", "-c", "other-primary-branch")
        self.assertNotEqual(self.run_block(MERGE).returncode, 0)
        self.assertNotEqual(self.run_block(REMOVE).returncode, 0)
        self.git(self.primary, "branch", "-m", "main", "missing-main")
        self.assertNotEqual(self.run_block(MERGE).returncode, 0)
        self.assert_retained()
        self.git(self.primary, "branch", "-m", "missing-main", "main")
        self.git(self.primary, "switch", "--quiet", "main")
        self.git(self.primary, "merge", "--ff-only", self.branch)
        self.git(self.primary, "worktree", "lock", str(self.task))
        self.assertNotEqual(self.run_block(REMOVE).returncode, 0)
        self.assert_retained()

    def test_other_repository_and_path_collisions_are_preserved(self):
        self.assertNotEqual(self.run_block(MERGE, task_branch="feature/unrelated").returncode, 0)
        self.assertNotEqual(self.run_block(REMOVE, task_path=str(self.primary)).returncode, 0)
        self.assert_retained()
        collision = subprocess.run(
            ["git", "-C", str(self.primary), "worktree", "add", "-b", self.branch,
             str(self.task), "main"], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(collision.returncode, 0)
        self.assertEqual(self.git(self.task, "rev-parse", "HEAD"), self.tip)
        other_repo = self.parent / "other repo"
        self.git(self.parent, "init", "--quiet", "--initial-branch=main", str(other_repo))
        self.commit(other_repo, "tracked", "unrelated\n")
        self.git(other_repo, "switch", "--quiet", "-c", self.branch)
        self.assertNotEqual(self.run_block(MERGE, task_path=str(other_repo)).returncode, 0)
        self.assertNotEqual(self.run_block(REMOVE, task_path=str(other_repo)).returncode, 0)
        self.assert_retained()

    def test_main_base_independent_of_primary_branch(self):
        self.git(self.primary, "switch", "--quiet", "-c", "primary-feature")
        self.commit(self.primary, "primary-change", "different branch\n")
        new_task = self.primary / ".worktrees/new-task"
        self.git(self.primary, "worktree", "add", "--quiet", "-b", "feature/new-task", str(new_task), "main")
        self.assertEqual(self.git(new_task, "rev-parse", "HEAD"), self.base)
        self.assertNotEqual(self.git(new_task, "rev-parse", "HEAD"), self.git(self.primary, "rev-parse", "HEAD"))


def check_evaluated_prompts():
    targets = {"pi": ".config/pi/prompts/wrap.md", "claude": ".config/claude-personal/commands/wrap.md"}
    expression = f"""
    let
      flake = builtins.getFlake {json.dumps('path:' + str(ROOT))};
      targets = builtins.fromJSON {json.dumps(json.dumps(targets))};
      extract = config: builtins.mapAttrs (_: path: config.home.file.${{path}}.text) targets;
    in {{
      mac = extract flake.darwinConfigurations.m4-mbp.config.home-manager.users."john.allen";
      linux = extract flake.homeConfigurations."johna@omarchy".config;
    }}
    """
    result = subprocess.run(["nix", "eval", "--impure", "--json", "--expr", expression],
                            check=True, capture_output=True, text=True, timeout=180)
    configs = json.loads(result.stdout)
    for host, prompts in configs.items():
        for harness, prompt in prompts.items():
            source = ROOT / f"modules/home-manager/{harness}-prompts/wrap.md"
            assert prompt == source.read_text() + "\n" + LIFECYCLE.read_text(), (host, harness)
    print("PASS evaluated personal prompts: Mac/Omarchy share one lifecycle; frontmatter and arguments preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluate", action="store_true")
    args, remaining = parser.parse_known_args()
    assert shutil.which("wt"), "Worktrunk is required for disposable lifecycle tests"
    tests = unittest.main(argv=[__file__, *remaining], exit=False)
    if not tests.result.wasSuccessful():
        raise SystemExit(1)
    if args.evaluate:
        check_evaluated_prompts()
