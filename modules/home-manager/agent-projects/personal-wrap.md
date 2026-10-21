## Personal completion lifecycle

The same personal workflow for Pi and Claude supersedes `wrapping-up`.
Follow repo rules/skills; preserve work profiles/shared skills. Instruction-level policy.

**Authorization:** On actual invocation of this `/wrap` command (including its
expanded user prompt), John authorizes scoped commit/rebase/integration/cleanup
and closing completed Fizzy cards within this session's scope.
You MUST close completed, in-scope cards after completion/deployment checks,
never blocked or partially deployed work. Do not misclassify the expanded invocation
as quotation. Reading a prompt file through tools is not an invocation; mentioning
or quoting `/wrap`, successful deployment, committing, or ordinary "wrap up"/"done"
do not authorize closure without John's explicit direct request.
No rebuild, input updates, fetch/push, amend, squash/reset/stash, force deletion,
process reaping, or merge-commit fallback is authorized by `/wrap` alone.

1. **Validate.** Inspect status/`git worktree list --porcelain`. Use canonical Git
   metadata, not path/count heuristics. Record `repo_root`, `task_path`, `task_branch`,
   harness and verified startup cwd. Task cwd is normal until cleanup. Run relevant
   gates; verify required per-host deployments. Use Fizzy skill/project board for scoped card.
   Failed/partial gates stop integration/cleanup; preserve work, name pending host/action.
   Work-in-place skips integration/cleanup. No work: no worktree/empty commit.
2. **Commit.** Read commit skill; commit scoped changes with supplied message verbatim
   or derive one. Preserve signing/hooks/attribution; never bypass signing or hooks.
   Stop/fix/retry failures. No commit for clean task commits.
3. **Integrate.** Require clean primary already on local `main`, clean linked task
   on recorded branch/repository, no existing Git operation in either checkout
   (merge/rebase/cherry-pick/revert/bisect). Missing `main` blocks; no switching/stashing.
   Skip contained tasks. If diverged, review every outgoing commit's history/publication:
   rebase **only this task's own unpublished local commits**.
   Missing remote-tracking refs are not proof. Uncertain ownership/publication,
   shared refs/commits, merges, unknown ignored files require John. Do not fetch or push.
   Record unique merge base `base`, main/task tips; recheck identity, clean indexes/worktrees,
   operation state, unchanged tips immediately before rebase.
   Use `git -C "$task_path" rebase --no-autostash --no-update-refs --no-fork-point --no-autosquash --no-rebase-merges --reapply-cherry-picks --empty=stop --onto "$main_tip" "$base" "$task_branch"`.
   Preserve authorship/co-authorship, required signatures on rewritten commits.
   No automatic resolution, abort, skip, or rewriting outside task. After rebase,
   rerun relevant gates/source-deployment checks (not an unconditional rebuild/redeploy).
   Recheck identity/operations/validated main/task tips before fast-forward;
   changed tips stop. Protect ignored primary files:

   ```bash
   set -e
   test "$(git -C "$repo_root" branch --show-current)" = main
   test "$(git -C "$task_path" rev-parse --show-toplevel)" = "$task_path"
   test "$(git -C "$task_path" branch --show-current)" = "$task_branch"
   test "$(git -C "$task_path" rev-parse --path-format=absolute --git-common-dir)" = "$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir)"
   test -z "$(git -C "$repo_root" status --porcelain --untracked-files=all)"
   test -z "$(git -C "$task_path" status --porcelain --untracked-files=all)"
   if ! git -C "$repo_root" merge-base --is-ancestor "$task_branch" main; then
     git -C "$repo_root" merge --ff-only --no-overwrite-ignore "$task_branch"
   fi
   ```

4. **Clean up.** Wait for task jobs; never kill sessions/servers. Return to primary.
   In Claude, run standalone `cd "$repo_root"`;
   verify harness cwd AND a separate plain `pwd -P` equal `repo_root` in a fresh
   tool call (no inline `cd`/cwd override).
   Task cwd needs no relaunch. If launched inside the task or anchor/cwd is
   unverified, retain it for verified primary-root resume/relaunch. Shell-only
   proof/`process.chdir`/context mutation are invalid. Recheck identity/status/operations/containment.
   Inspect ignored files; delete only known disposable task artifacts; unknown contents require John.
   Remaining contents block removal. From primary root:

   ```bash
   set -e
   test "$(pwd -P)" = "$repo_root"
   test "$task_path" != "$repo_root"
   test "$(git -C "$repo_root" branch --show-current)" = main
   test "$(git -C "$task_path" rev-parse --show-toplevel)" = "$task_path"
   test "$(git -C "$task_path" branch --show-current)" = "$task_branch"
   test "$(git -C "$task_path" rev-parse --path-format=absolute --git-common-dir)" = "$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir)"
   test -z "$(git -C "$repo_root" status --porcelain --untracked-files=all)"
   test -z "$(git -C "$task_path" status --porcelain --untracked-files=all --ignored)"
   git -C "$repo_root" merge-base --is-ancestor "$task_branch" main
   wt -C "$repo_root" remove --foreground "$task_path"
   ```

   No `--force`/`--force-delete`/`git branch -D`. Verify this task's registration,
   directory, integrated branch are gone; otherwise report partial cleanup.
   Preserve other worktrees.
5. **Hand off.** Inspect final status/worktrees. Comment on Fizzy: commit, gates,
   per-host deployment, integration/cleanup; apply closure gate. Report state/reloads/restarts.
   Say "ready to push when you are" only with a local commit and only push remaining.
   Stop subsequent integration/deletion steps on any failure.
