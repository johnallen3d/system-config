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
- Preserve all applicable safety, profile, credential, issue-tracking,
  authorization, and deployment gates for the actual task. Do not use
  proportionality to bypass them.
