---
description: "Review current issue work with parallel reviewers. Usage: /issue-review <issue-url|#123|issue text> [review focus]"
argument-hint: "<issue-url|#123|issue text> [review focus]"
model: gpt-5.4
---

Issue/ref: $1
Focus: ${@:2}

Review only. No fixes unless I ask.

Flow:
1. Read issue.
2. Inspect current impl/diff.
3. Run parallel fresh `reviewer` passes for:
   - correctness/regressions;
   - tests/validation;
   - simplicity/maintainability;
   - issue requirement match.
4. Return:
   - fix now;
   - optional improve;
   - ignore/defer, with short why.

Require evidence + file/line refs.
