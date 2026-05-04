---
description: "Implement a GitHub issue with planning + review. Usage: /issue-implement <issue-url|#123|issue text> [extra context]"
argument-hint: "<issue-url|#123|issue text> [extra context]"
model: gpt-5.4
skill: issue-driven-implementation
---

Issue/ref: $1
Extra: ${@:2}

Use the loaded `issue-driven-implementation` skill fully. Carry the workflow through PR creation, not just code changes or commit prep, unless repo policy or explicit user instruction says otherwise.

Flow:
1. Read issue.
2. `scout` local code.
3. `researcher` only if external docs/API/lib matter.
4. `planner` make explicit plan.
5. Summarize plan before code.
6. `worker` implement approved scope.
7. Run parallel fresh `reviewer` passes for:
   - correctness/regressions;
   - tests/validation;
   - simplicity/maintainability;
   - issue requirement match.
8. Synthesize review.
9. `worker` apply worthwhile in-scope fixes.
10. Create or update PR for the issue work when policy allows.
11. Finish with:
   - changed files;
   - validation run;
   - PR link/status;
   - remaining risks/follow-ups;
   - concise GitHub issue comment and PR summary.

Prefer short-lived subagents. Prefer fresh reviewers. Stay in issue scope.
