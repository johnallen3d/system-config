## Task scope and proportionality

- Treat John's requested outcome as the scope boundary. Workflow rules constrain
  authorized work; they do not authorize extra deliverables.
- Before adding repository edits, worktrees, documentation, tests, deployment, or
  investigation, identify why the requested outcome requires them. If optional,
  leave them out; ask before expanding scope.
- Check ownership of the exact target. A direct operation on a user-owned file
  outside a repository needs no repository edits or worktree. A Nix-managed file
  still requires its declarative source and deployment workflow.
- Use the smallest verification that proves the requested result. Do not replace
  outcome verification with an unrelated full-project workflow.
- A failed optional check is not a blocker for the requested operation. Stop the
  optional branch; do not debug dependencies created by scope expansion.
- An authorized deployment includes clean, guarded fast-forward synchronization
  of a deployment host's `main` to reviewed, already-integrated local `main`.
  Do not ask for separate merge permission for that synchronization; it is an
  exception to the general merge-authorization rule. Stop on dirty source,
  divergence, conflicts, or uncertain ownership. This does not authorize task
  branch integration, new commits, rebases, pushes, or worktree removal.
- Preserve all applicable safety, profile, credential, issue-tracking,
  authorization, and deployment gates for the actual task. Do not use
  proportionality to bypass them.
