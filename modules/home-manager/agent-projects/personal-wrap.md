## Personal completion lifecycle

This shared Pi/Claude workflow supersedes `wrapping-up`; follow repository rules
and personal worktree, attribution, and deployment policies.

Actual `/wrap` invocation (including its expanded prompt) authorizes scoped
commit, guarded rebase, fast-forward integration, safe cleanup, and closing
every Fizzy card linked to or covered by the task. Reading or mentioning it does not.
It also authorizes a plain `git push` of integrated local `main` (step 4),
unless invoked as `/wrap no-push` or John said not to push this session.
It does not authorize fetch, force push, pushing other refs, input updates,
amend/squash/reset/stash,
force deletion, killing processes, or bypassing hooks/signing. Deployment is
authorized only where the repository's `AGENTS.md` says `/wrap` deploys; then
it follows that repository's deployment rules.

1. **Validate and commit.** Inspect status and canonical worktree metadata;
   identify this task's repository, branch, worktree, and session start directory.
   Run only relevant code gates. Read the canonical commit skill and verify
   implementation attribution. Cards are normally created when the task starts;
   as a fallback, if the repository tracks work in Fizzy and still no card
   covers this task, create one describing the completed work now. Link
   every card or issue the task covers with `switchyard link REF` while the
   branch still exists (`switchyard-links` skill), and reference them in the
   commit. Commit scoped changes only; no empty commits.
2. **Integrate.** Require clean primary already on local `main`, clean task
   checkout on its recorded branch in the same repository, and no Git operation
   in progress. Skip already-contained tasks. If diverged, rebase only verified
   task-owned unpublished local commits onto local `main`; uncertainty, shared
   history, merges, or conflicts stop. Preserve attribution/signatures; no
   automatic conflict handling or unrelated ref updates. Rerun relevant gates.
   Recheck identity, cleanliness, operation state, and unchanged validated tips;
   integrate with `git merge --ff-only --no-overwrite-ignore`.
3. **Clean up.** First return to the primary checkout. In Claude, run a standalone
   `cd "$repo_root"`, then verify the harness cwd and a fresh `pwd -P` in a separate
   call. If the session was launched inside the task worktree (Rex spawn tabs
   are), `cd` does not move its anchor: skip removal. If John asked to archive,
   the archive below removes it; otherwise report the worktree as left for
   archive. That is not a blocker once commit and integration succeed. A subshell,
   command cwd override, `wt switch`, or Pi `process.chdir` is not proof of a
   safe cwd. Never delete the running session's directory; retain the worktree
   if the session anchor or cwd is uncertain. Wait for task
   jobs. Inspect ignored files: leave known disposable build output (`target/`,
   etc.) for worktree removal, not separate deletion. Unknown or valuable ignored
   contents require John. Recheck task identity, clean status (excluding ignored
   files), and containment in `main`; then use `wt remove --foreground` from
   primary. Never force. Verify this task's worktree and branch are gone.

   **When John asks to archive this session, archive it — unless this wrap is
   blocked (`WRAP BLOCKED`).** A wrap never archives on its own. When wrap
   succeeds and John asked to archive, carry it out immediately with
   `switchyard stop_task` for this task without asking again or handing it back
   to John (no "archive it from the picker"). Close linked cards first (step 4);
   archiving never substitutes for closing. Non-blockers — pending lock updates,
   unapproved follow-ups, or a failed/opted-out push — go in the handoff and do
   not withhold the archive. **If any required step hits a blocker (`WRAP
   BLOCKED` — e.g. merge/rebase conflict, dirty primary, failed required check,
   or failed/unreachable deploy host), DO NOT archive even if John asked to
   wrap and archive:** leave the session open so John can act on the blocker,
   and archive only if John explicitly asks to archive anyway afterwards. The
   only other gate is `stop_task` refusing uncommitted changes; if it refuses,
   report that. Archive as the last action: first write the full handoff as
   text, since closing the tab ends the session.
4. **Hand off.** Report final status, commit, integration/cleanup, push, and
   deployment separately. **Push.** Unless opted out, after integration (and
   deployment, where it applies) run `git -C "$repo_root" push` for local `main`
   to its configured upstream: no `--force`, no fetch, no other refs. Skip it
   when `main` has no upstream or nothing new to push. A rejected or failed push
   is reported as pending (`ready to push when you are`), not a wrap blocker;
   never fetch, pull, or rebase to make it succeed. Work-in-place pushes the
   committed branch the same way only if it is `main`. **Deploy, where the repository requires it.** If `AGENTS.md` says
   `/wrap` deploys and the commit changes shared config, run that deployment after
   integration and before cleanup, following the repository's deployment rules.
   **Close every card.** A wrap ends with every card linked to or covered by the
   task closed (`fizzy card close NUMBER`), with a comment naming the commit, or
   the outcome when there is no commit. Leaving a card open is a failure John has
   to clean up later, not a cautious default. Tasks without a commit (operational,
   user-action, investigation) close too once the outcome holds. Before treating
   any card as incomplete, re-check its live state now (rerun the status command,
   query the host); observations from earlier in the session are stale. Scope John
   narrows during the task or the wrap ("not doing X for now") counts as done for
   the dropped part; say so in the closing comment. The only reason to keep a card
   open is a freshly re-verified blocker: a failed or unreachable deploy host, or
   a required check that ran and failed. Then report WRAP BLOCKED, name the host
   or check, and do not archive — leave the session open so John can resolve it. Never finish with untracked work. Push does not
   block Git integration or cleanup, but required acceptance checks still apply.
   Link follow-ups and name pending hosts/actions. Work-in-place skips integration
   and cleanup. Any failure stops subsequent integration/deletion steps.

   **Testing gaps are John's call, not a blocker.** A deployment that succeeded
   on every host, with the installed artifact or config confirmed, counts as
   deployed. If behaviour was exercised on fewer hosts than it was deployed to
   (e.g. an interactive picker tried by hand only on the Mac), close the card and
   state in the handoff exactly what was tested where. Don't block the wrap, keep
   the card open, or ask permission over it; John decides whether more testing
   matters. Only an actual failure (failed deploy, unreachable host, a check
   that ran and failed) makes deployment partial.

   **Go-aheads count.** During an active `/wrap`, if you did stop to ask John,
   any affirmative reply ("wrap it up", "just do it", "yes", "close it") answers
   the pending question and authorizes finishing within this lifecycle's limits.
   Don't ask for specific wording.

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
  `/wrap` in this task's session). State that wrap has not automatically resumed,
  and leave the session unarchived (do not call `switchyard stop_task`) even if
  John asked to archive as part of `/wrap`.

Then briefly list what did succeed, the commit if any, retained branch/worktree,
per-host deployment status when applicable, and the card left open. Never lead
with "done", "fixed", "completed", or "ready to push" while a required step is
blocked. Optional follow-up work and a failed or opted-out push are not wrap blockers.
This reporting requirement changes no authorization or safety gates above.
