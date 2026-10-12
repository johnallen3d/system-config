## Personal completion lifecycle

This is the same personal workflow for Pi and Claude. It replaces the shared
`wrapping-up` skill's PR-only cleanup, force-removal retry, premature card closure,
and unconditional ready-to-push message. Do not invoke that workflow end-to-end.
Do not modify work-profile instructions or the user-owned shared skill.

Only an actual personal `/wrap` invocation, including its expanded user prompt,
authorizes the following commit, local integration, and cleanup sequence. Merely
reading this prompt, mentioning `/wrap`, or ordinary "wrap up" language does not.
This authorization includes only the guarded rebase of this task's own unpublished
local commits described below, never published/shared history or another branch.
It never includes a rebuild, fetch, push, squash, reset, stash, force deletion,
process reaping, or a merge-commit fallback.

1. **Identify the task.** Inspect Git status and `git worktree list --porcelain`.
   Resolve canonical primary/task paths through Git metadata, not pathname
   heuristics or the number of worktrees. Record the absolute `repo_root`,
   `task_path`, and `task_branch` for this session's task; never choose an unrelated
   worktree just because it is the only one listed. Load applicable repository
   instructions. For an explicit work-in-place opt-out, validate and commit only
   the scoped changes, then report status; skip integration and cleanup. If there
   is no task worktree and no scoped change, do not invent one or make an empty
   commit.
2. **Validate and track.** Run relevant quality gates. Check any required
   deployments and installed verification; `/wrap` alone does not authorize
   deployment. Wait for this task's workers and background jobs to finish before
   cleanup; do not kill other sessions or servers. Use the Fizzy skill, selected
   project board, and `fizzy card list --all --jq '[.data[] | {number, title}]'` to
   find the task card; create one only if necessary. Document progress, but defer
   closure until all completion gates below are satisfied. Blocked or partially
   deployed work stays open, with the pending host/action named.
3. **Commit in the task worktree.** Review staged and unstaged changes and recent
   commit conventions. Stage specific intended files only; preserve unrelated
   staged changes and do not accidentally include them in the commit. If the
   index contains unrelated work, stop for John's decision rather than changing
   it. Follow repository signing/hooks and attribution rules. Use a supplied
   commit message without adding a conventional prefix, or derive one if absent.
   Create a new commit, never amend or create an empty commit. A hook failure is
   a stop/fix/retry, not permission to bypass the hook. Existing clean task commits
   can be integrated without another commit. If validation/deployment is blocked,
   report that state and preserve the task worktree; do not proceed to integration
   or cleanup.
4. **Fast-forward local main.** Require the primary checkout to be clean and
   already on local `main`; do not switch someone else's checkout or stash its
   changes. Require the task worktree to be clean, on its recorded branch, and
   linked to this same repository, with no merge/rebase/cherry-pick/revert or
   bisect in progress in either checkout. Verify primary/task identity using the
   recorded canonical paths and Git metadata; a linked checkout cannot stand in
   for the primary. Missing `main` remains a blocker.

   If main advanced independently, an actual personal `/wrap` permits a bounded
   rebase of **only this task's own unpublished local commits** onto existing
   local `main`. Review every outgoing commit against recorded task history and
   existing publication evidence; absence from remote-tracking refs alone is not
   proof. Uncertain ownership/publication, shared commits or refs, merge commits,
   or unknown ignored task files require John's decision. Do not fetch or push
   to establish publication status. Record the reviewed main/task tips and unique
   merge base, then recheck identity, both clean indexes/worktrees, no existing
   Git operation, and unchanged tips immediately before rebasing.

   Use `git -C "$task_path" rebase --no-autostash --no-update-refs --no-fork-point --no-autosquash --no-rebase-merges --reapply-cherry-picks --empty=stop --onto "$main_tip" "$base" "$task_branch"`.
   Preserve authorship/co-authorship and repository signing/hooks, including
   required signatures on rewritten commits; never bypass signing or hooks.
   Never rewrite main, published/shared history, or another task's branch/worktree.
   On conflict, signing/hook failure, or an empty-commit stop, preserve the task
   worktree and operation and report the failing step and affected paths. No
   automatic resolution, abort, skip, stash/reset/squash, or merge fallback.

   After rewriting, rerun relevant gates, verify attribution/signatures, and
   recheck resulting source/deployment compatibility on each required host,
   including incoming main changes. Unchanged deployed content needs verification,
   not an unconditional rebuild/redeploy; `/wrap` alone grants no deployment or
   input updates. Failed gates or partial deployment stop integration/cleanup.
   Recheck identity, clean status, no operation, and validated main/task tips
   before fast-forwarding; if a tip changes, stop rather than automatically
   rebasing again.

   Protect ignored primary-checkout contents with `--no-overwrite-ignore`;
   a task that would overwrite them must stop without advancing `main`.
   If the task branch is already contained in `main`, skip integration; otherwise
   require a fast-forward (after any authorized rebase and renewed gates):

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

   Verify `git -C "$repo_root" merge-base --is-ancestor "$task_branch" main`.
   An already-integrated task needs no new commit or history rewriting.
5. **Verify the real session cwd.** Both harnesses normally stay anchored at the
   primary repository root while task operations target explicit worktree paths.
   Verify the harness's current-directory context and a separate plain `pwd -P`
   tool call with no preceding `cd` or cwd override; both must resolve to
   `repo_root`. Do not use a shell's `wt switch`, `process.chdir`, or a context
   mutation as proof of an agent-session cwd change. If the session was launched
   or moved inside the task worktree, retain it and ask John to resume/relaunch
   at the primary root. Do not claim automatic cleanup or delete the active cwd.
6. **Remove only the completed worktree.** Recheck task identity, clean primary
   and task status, and containment of the recorded branch in `main`. Inspect
   `git -C "$task_path" status --short --untracked-files=all --ignored` before
   deletion: preserve unknown tracked, untracked, and ignored files. Remove only
   known disposable artifacts created by this task; unknown contents require
   John's decision. Refuse cleanup while any such contents remain. Use installed
   Worktrunk for synchronous, non-forced cleanup from the primary root:

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

   Never retry with `--force` or `--force-delete`, use `git branch -D`, or reap
   processes. Verify the exact task worktree is unregistered, its directory is
   gone, and its integrated local branch is deleted. If Worktrunk retained a
   branch or removal failed, report partial cleanup rather than claiming success;
   never broaden cleanup to other worktrees.
7. **Complete the handoff.** Run final Git status and worktree inspection. Add a
   Fizzy comment recording commit, integration, cleanup, validation, and separate
   host deployment outcomes. Apply the closure authorization invariant above:
   MUST close completed, in-scope cards only after all relevant completion and
   deployment gates, never blocked or partially deployed work. Report the actual
   commit, local-main integration, primary-root cwd, and cleanup outcomes. Say
   "ready to push when you are" only if a local commit exists and push is the sole
   remaining step; otherwise name the remaining work. Never push automatically.

Stop subsequent integration/deletion steps on any failure, preserve remaining
work, and report the blocker. These are agent instructions, not a harness-enforced
write or cleanup restriction.
