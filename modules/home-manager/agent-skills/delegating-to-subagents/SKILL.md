---
name: delegating-to-subagents
description: Use when John explicitly asks for a sub-agent or delegation, and when a delegated task fails, times out, or returns incomplete work.
---

# Delegating to sub-agents

## Launch

- Delegation is the parent's first substantive action. Before launching, do only
  minimal launch discovery (finding the delegation tool and its requirements):
  no task file or other skill reads, investigation, search, Fizzy actions, edits,
  or tests. Those belong to the child.
- Brief the child briefly: John's request and the authorization boundaries.
  Preserve the inherited working directory, profile, and environment, including
  `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`; never switch profiles or copy
  credentials. Tell the child to read applicable instructions and skills itself
  and to handle investigation, authorized implementation, issue tracking, and
  validation. Delegation authorizes nothing extra.
- Ask for only a concise outcome, card link, blockers, and decisions — no
  transcripts, raw logs, or file dumps.

## After the handoff

- Relay the result. Do not investigate or execute the task in the parent without
  John's explicit permission, except the recovery inspection below.

## Recovery

- The parent owns recovery from unavailable or failed delegation. First inspect
  partial results and reconcile possible side effects with narrowly scoped,
  read-only inspection. Reuse completed work; never blindly replay writes.
- Allow one corrective delegated attempt within the original scope, permissions,
  budget, and inherited profile/environment. Fixing an agent-caused timeout or
  launch mistake needs no fresh approval. Never run the task in the parent,
  silently fall back, or retry under a different profile.
- If safe recovery is blocked, the corrective attempt fails, or continuing needs
  new authorization, stop, report the blocker, and ask John. Never override user
  cancellation, deliberate deadlines, or permission denials.
