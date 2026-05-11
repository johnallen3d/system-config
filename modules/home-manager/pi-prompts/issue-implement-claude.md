---
description: "Implement a GitHub issue with planning + Claude subagents for heavy lifting. Usage: /issue-implement-claude <issue-url|#123|issue text> [extra context]"
argument-hint: "<issue-url|#123|issue text> [extra context]"
model: gpt-5.4
skill: issue-driven-implementation
---

Issue/ref: $1
Extra: ${@:2}

Use the loaded `issue-driven-implementation` skill fully. You are the orchestrator running on gpt-5.4.
Delegate heavy tasks to Claude via the AskClaude tool as specified below.
Carry the workflow through PR creation unless repo policy or explicit user instruction says otherwise.

Flow:

1. Read the issue.

2. **scout** — call AskClaude:
   - model: haiku, mode: read, thinking: off, isolated: true
   - Task: explore and summarize the relevant local code: entry points, affected files, interfaces, and anything the planner needs to know.
   - Bring the full summary back into this conversation.

3. **researcher** (only if external docs/API/lib matter) — call AskClaude:
   - model: sonnet, mode: read, thinking: low, isolated: true
   - Task: fetch and synthesize relevant external documentation or API references.
   - Bring the summary back into this conversation.

4. **planner** — you (gpt-5.4) produce an explicit implementation plan using the scout and researcher output. No AskClaude needed; you have full context.

5. Summarize the plan to the user before any code changes.

6. **worker** (implementation) — call AskClaude:
   - model: sonnet, mode: full, thinking: medium, isolated: false
   - Task: implement the approved plan exactly. Write, edit, and run code as needed.
   - Pass the approved plan clearly in the prompt so Claude has the full scope.

7. Run four **reviewer** passes in parallel — each as a separate AskClaude call:
   - All reviewers: model: opus (correctness) or sonnet (others), mode: read, isolated: true
   - **Correctness/regressions**: model: opus, thinking: high — find logic errors, edge cases, regressions.
   - **Tests/validation**: model: sonnet, thinking: medium — assess test coverage, missing assertions, validation gaps.
   - **Simplicity/maintainability**: model: sonnet, thinking: low — flag over-engineering, dead code, clarity issues.
   - **Requirement match**: model: haiku, thinking: off — mechanical check: does the code satisfy every item in the issue?
   - Each reviewer prompt must include the issue text and the diff/changed files.

8. Synthesize all reviewer feedback. Decide which findings are worthwhile and in-scope.

9. **worker** (fixes) — if fixes are needed, call AskClaude:
   - model: sonnet, mode: full, thinking: low, isolated: false
   - Task: apply only the in-scope fixes identified in step 8. No scope creep.

10. Create or update a PR for the issue work when policy allows.

11. Finish with:
    - changed files;
    - validation run;
    - PR link/status;
    - remaining risks/follow-ups;
    - concise GitHub issue comment and PR summary.

Stay in issue scope. Prefer isolated reviewers. Pass full context in each AskClaude prompt.
