## Personal completion lifecycle

This shared Pi/Claude workflow supersedes `wrapping-up`; follow repository rules
and personal worktree, attribution, and deployment policies.

Actual `/wrap` invocation (including its expanded prompt) authorizes scoped
commit, guarded rebase, fast-forward integration, safe cleanup, and closing
completed in-scope Fizzy cards. Reading or mentioning it does not.
It does not authorize push/fetch, deployment, input updates, amend/squash/reset/stash,
force deletion, killing processes, or bypassing hooks/signing.

1. **Validate and commit.** Inspect status and canonical worktree metadata;
   identify this task's repository, branch, worktree, and session start directory.
   Run only relevant code gates. Read the canonical commit skill and verify
   implementation attribution. Commit scoped changes only; no empty commits.
2. **Integrate.** Require clean primary already on local `main`, clean task
   checkout on its recorded branch in the same repository, and no Git operation
   in progress. Skip already-contained tasks. If diverged, rebase only verified
   task-owned unpublished local commits onto local `main`; uncertainty, shared
   history, merges, or conflicts stop. Preserve attribution/signatures; no
   automatic conflict handling or unrelated ref updates. Rerun relevant gates.
   Recheck identity, cleanliness, operation state, and unchanged validated tips;
   integrate with `git merge --ff-only --no-overwrite-ignore`.
3. **Clean up.** Follow the personal session-cwd safety checks before removal;
   retain the worktree if the session anchor or cwd is uncertain. Wait for task
   jobs. Inspect ignored files: leave known disposable build output (`target/`,
   etc.) for worktree removal, not separate deletion. Unknown or valuable ignored
   contents require John. Recheck task identity, clean status (excluding ignored
   files), and containment in `main`; then use `wt remove --foreground` from
   primary. Never force. Verify this task's worktree and branch are gone.
4. **Hand off.** Report final status, commit, integration/cleanup, and deployment
   separately. Close completed in-scope cards; keep blocked or partially deployed
   cards open. If the repository tracks work in Fizzy and no card covers this
   task, create one describing the completed work before closing it; never
   finish with untracked work. Follow repository release order: later push/deployment does not
   block Git integration or cleanup, but required acceptance checks still apply.
   Link follow-ups and name pending hosts/actions. Work-in-place skips integration
   and cleanup. Any failure stops subsequent integration/deletion steps.

### Blocked outcome — make it impossible to mistake for success

If a required lifecycle step fails, cannot safely proceed, or leaves required
acceptance/deployment incomplete, announce it immediately. Start the final reply
with this plain-text box in a fenced code block, before any success summary:

```text
+------------------------------------+
|     WRAP BLOCKED - NOT COMPLETE     |
+------------------------------------+
```

Do not rely on color, ANSI escapes, or a buried bullet. Immediately below the box,
state these fields, using concrete paths, hosts, and actions where relevant:

- **Blocker:** the failed/stopped step and exact reason.
- **Not finished:** required stages still pending, including later stages skipped.
- **Impact:** what John still cannot use or rely on. Explicitly distinguish
  deployed changes from source integrated into `main`; a successful deployment
  does not mean the normal checkout entry point contains the fix. If only cleanup
  is blocked, say so rather than implying the implementation is broken.
- **Next action:** the smallest safe unblock action and who can take it. Ask one
  targeted question if John's decision or new authorization is required; never
  suggest discarding unrelated changes or bypassing a safety gate.
- **Resume:** how to continue after the blocker is resolved (normally rerun
  `/wrap` in this task's session). State that wrap has not automatically resumed.

Then briefly list what did succeed, the commit if any, retained branch/worktree,
per-host deployment status when applicable, and the card left open. Never lead
with "done", "fixed", "completed", or "ready to push" while a required step is
blocked. Optional follow-up work and an unrequested push are not wrap blockers.
This reporting requirement changes no authorization or safety gates above.
