## Explicit sub-agent requests: delegate first

- When John explicitly asks for a sub-agent or delegation, delegation must be the
  parent's first substantive action. Before launching the child, the parent may
  perform only minimal launch discovery (such as finding the delegation tool or
  its invocation requirements). Do not read task files or skills, investigate,
  search, act on Fizzy cards, edit, or test before delegation. Applicable skill
  reads and task-specific setup belong to the child, not the parent.
- Give the child a short brief with John's request and authorization boundaries.
  Preserve the inherited working directory, profile, and environment, including
  `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`; do not switch profiles or copy
  credentials. Tell the child to read applicable instructions and skills itself,
  then handle investigation, authorized implementation, issue tracking, and
  validation. Delegation does not authorize additional actions.
- Request only a concise outcome, card link (when applicable), blockers, and
  decisions for the parent. Do not return transcripts, raw logs, or file dumps.
  The parent may relay that handoff, but must not independently investigate or
  execute the underlying task without John's explicit permission, except for the
  narrowly scoped read-only recovery inspection below.
- The parent owns recovery from unavailable or failed delegation, not just
  reporting failure. First inspect partial results/checkpoints and reconcile
  possible side effects through narrowly scoped read-only parent inspection
  for recovery only, not independent execution of the underlying task. Reuse
  completed work; never blindly replay writes.
- Allow one corrective delegated attempt within the original scope, permissions,
  budget, and inherited profile/environment, including `PI_CODING_AGENT_DIR` and
  `CLAUDE_CONFIG_DIR`. Correcting an agent-created timeout or launch mistake does
  not require fresh approval within those boundaries. Do not execute the task
  in the parent, silently fall back, or retry by changing the inherited profile.
- Stop, report the blocker, and ask John when safe recovery is blocked, the
  corrective attempt fails, or continuation needs new authorization. Never
  override user cancellation, deliberate deadlines, or permission denials.
- This is instruction-level policy, not a hard guarantee or a harness-enforced
  restriction on parent tools. A separate enforced delegation mode would require
  its own implementation and authorization.
