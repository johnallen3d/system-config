---
description: "Implement a GitHub issue with planning + review. Usage: /issue-implement <issue-url|#123|issue text> [extra context]"
argument-hint: "<issue-url|#123|issue text> [extra context]"
model: opus
---

Issue/ref: `$1`
Extra: rest of `$ARGUMENTS` after `$1`.

Invoke the `issue-driven-implementation` skill and carry its workflow through PR creation (not just code changes or commit prep), unless repo policy or explicit user instruction says otherwise.

Flow:

1. Read the issue.
2. Dispatch a fresh `scout` subagent to map relevant local code.
3. Dispatch a fresh `researcher` subagent if external docs / API / library behavior matters.
4. Dispatch a `planner` subagent to produce an explicit plan from scout + researcher output.
5. Summarize the plan to the user **before** any code changes; pause for confirmation if scope is non-trivial.
6. Dispatch a `worker` subagent to implement the approved scope.
7. Dispatch parallel fresh `reviewer` subagents — one per focus, in a single message:
   - correctness / regressions;
   - tests / validation;
   - simplicity / maintainability;
   - issue requirement match.
8. Synthesize reviewer reports.
9. Dispatch a `worker` subagent to apply worthwhile in-scope review fixes.
10. Create or update the PR for the issue work when repo policy allows.
11. Finish with:
    - changed files;
    - validation run + results;
    - PR link / status;
    - remaining risks / follow-ups;
    - concise GitHub issue comment + PR summary.

Prefer short-lived subagents. Prefer fresh reviewers (one focus each). Stay strictly in issue scope.
