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
  The parent may relay that handoff, but must not independently investigate the
  task without John's explicit permission.
- If delegation is unavailable or fails, report the blocker and stop. Do not
  execute the task in the parent, silently fall back, or retry by changing the
  inherited profile. Parent investigation requires John's explicit permission.
- This is instruction-level policy, not a hard guarantee or a harness-enforced
  restriction on parent tools. A separate enforced delegation mode would require
  its own implementation and authorization.
