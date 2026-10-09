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
- Create every new task worktree from `main`, never from the current branch or
  another base. Use a simple kebab-case task slug, e.g. `add-xyz-feature`, with no
  branch prefix or path separators in the slug. The worktree must be at the
  repository's `.worktrees/<slug>` (e.g. `.worktrees/add-xyz-feature`), and its
  task-specific branch must always be `feature/<slug>` (e.g.
  `feature/add-xyz-feature`), including fixes and chores.
- If already in a linked worktree for this task that follows this convention,
  use it. Otherwise create it with the following command, where `repo_root` is
  the absolute path to the repository's primary checkout and `slug` is the task
  slug:

  ```bash
  git -C "$repo_root" worktree add -b "feature/$slug" "$repo_root/.worktrees/$slug" main
  ```

  Then run all edits, builds, tests, and Git commands from that worktree. Do not
  switch branches or perform task changes in the primary checkout. If `main` is
  unavailable or the branch/path already exists and is unsuitable for this task,
  stop and report the blocker; do not substitute another base, prefix, or path.

- Keep work repositories beneath `~/dev/src/amfaro` so their `.worktrees/`
  descendants retain the shared mise work profile. For repositories elsewhere,
  explicitly preserve both work profile variables and the project's mise tool
  context. Use `mise exec` explicitly for noninteractive work commands; `cd` alone
  does not activate mise there.
- Preserve existing uncommitted changes and other tasks' worktrees. Do not move,
  discard, reset, or clean up someone else's changes to make a worktree usable.
  If safe worktree setup is blocked, stop and report the blocker instead of
  falling back to the primary checkout.
- Never commit, merge, push, or remove a worktree unless explicitly requested.
