---
description: "Plan a GitHub issue with subagents. Usage: /issue-plan <issue-url|#123|issue text> [extra context]"
argument-hint: "<issue-url|#123|issue text> [extra context]"
model: opus
---

Issue/ref: `$1`
Extra: rest of `$ARGUMENTS` after `$1`.

No code. No edits.

Flow:

1. Read the issue (gh CLI for GitHub, `bd show` for beads, or the literal text if given inline).
2. Dispatch a fresh `scout` subagent (via `Agent` tool, `subagent_type: scout`) to map relevant local code.
3. If external docs / API / library behavior matters, dispatch a fresh `researcher` subagent in parallel.
4. Dispatch a `planner` subagent with the scout + researcher output to produce an explicit plan.
5. Return:
   - issue read (summary + link/id);
   - key files/modules touched;
   - risks / unknowns;
   - step plan with verifications;
   - validation plan;
   - draft GitHub issue comment containing the execution plan.

Prefer short-lived subagents. Prefer fresh `scout` / `researcher` per invocation — don't reuse context across phases. Keep the final output concrete, ready to execute.
