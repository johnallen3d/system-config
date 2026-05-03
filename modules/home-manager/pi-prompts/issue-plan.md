---
description: "Plan a GitHub issue with subagents. Usage: /issue-plan <issue-url|#123|issue text> [extra context]"
argument-hint: "<issue-url|#123|issue text> [extra context]"
model: gpt-5.4
---

Issue/ref: $1
Extra: ${@:2}

No code.

Flow:
1. Read issue.
2. `scout` local code.
3. `researcher` only if external docs/API/lib matter.
4. `planner` make explicit plan.
5. Return:
   - issue read;
   - key files/modules;
   - risks/unknowns;
   - step plan;
   - validation plan;
   - GitHub issue comment draft for execution plan.

Prefer short-lived subagents. Prefer fresh `scout`/`researcher`. Keep output concrete, ready to execute.
