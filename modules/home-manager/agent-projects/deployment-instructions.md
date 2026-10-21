## Concurrent tasks and deployments

- Concurrent agents and task worktrees are normal. Before activation, discover
  the host's active generation, recorded source/task owners, and in-flight
  deployment. Use the project's coordinator/status command where available.
  For system-config, use `mise exec -- system-config-deploy "$task_path"
  --switch-only` (Mac applies both hosts; Omarchy is host-local). The installed
  coordinator also supports older task worktrees; do not run their pre-lock
  activation scripts. Inspect status with the installed coordinator script
  `~/.local/share/system-config-deploy/.mise/scripts/deployment_state.py`
  (`python3 SCRIPT status "$task_path"`).
  A difference from `main` is not permission to revert active work, nor a reason
  to make John broker routine nonconflicting coordination.
- Preserve only verified, already-active task changes, not every dirty worktree
  or pending implementation. Compose deployment source in an automatically cleaned
  temporary directory backed by pinned Git snapshots, not another linked worktree.
  Leave task branches, indexes, source worktrees, and credentials alone.
  Carrying a verified active overlay is not committing or integrating its task.
- Use the same host-wide activation lock for all deployment entry points. Wait
  for its owner or retry after it finishes; do not bypass it, kill another agent,
  or restart active agents to obtain a fresh environment. Re-read provenance
  under the lock, and retain it through activation and outcome recording.
- Escalate only a precise blocker: overlapping paths with their task owners,
  unrecorded activation/rollback, unreproducible source, uncertain ownership, or
  missing authorization. Investigate ordinary provenance recovery yourself:
  adoption requires an exact evaluated-output match to the installed generation
  plus verified task ownership. Never guess from worktree timestamps or adopt
  unactivated changes merely because a build succeeds.
- Deployment composition never authorizes commits, task-branch merges/rebases,
  pushes, worktree removal, service restarts, or closure of another task's card.
  Preserve per-host verification and report partial deployments explicitly.
