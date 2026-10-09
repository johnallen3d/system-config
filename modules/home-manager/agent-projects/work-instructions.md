# Work agent instructions

- Always respond in English. The user's name is John Allen.
- John works for gmatter as a software architect with additional DevOps responsibilities.
- Respect both `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`. Never use or copy
  personal credentials or sessions into the work profile.

## Git worktrees are required

- Always perform repository changes in a dedicated **linked Git worktree** on a
  task-specific branch, unless John explicitly authorizes a primary-checkout edit.
  A feature branch in the primary checkout is not sufficient.
- Before editing repository files or running commands that write to the repository,
  verify the current checkout with `git worktree list --porcelain` and
  `git rev-parse --path-format=absolute --git-dir --git-common-dir`. In a linked
  worktree, the Git directory differs from the common Git directory. Resolve
  symlinks before comparing paths.
- If already in a suitable linked worktree for this task, use it. Otherwise create
  a task-specific branch and linked worktree from the appropriate base, then run
  all edits, builds, tests, and Git commands from that worktree. Do not switch
  branches or perform task changes in the primary checkout.
- Prefer worktree locations beneath `~/dev/src/amfaro` so the shared mise work
  profile remains active. For worktrees elsewhere, explicitly preserve both work
  profile variables and the project's mise tool context. Use `mise exec` explicitly
  for noninteractive work commands; `cd` alone does not activate mise there.
- Preserve existing uncommitted changes and other tasks' worktrees. Do not move,
  discard, reset, or clean up someone else's changes to make a worktree usable.
  If safe worktree setup is blocked, stop and report the blocker instead of
  falling back to the primary checkout.
- Never commit, merge, push, or remove a worktree unless explicitly requested.
