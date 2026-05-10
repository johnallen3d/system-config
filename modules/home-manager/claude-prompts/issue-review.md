---
description: "Review current issue work with parallel reviewers. Usage: /issue-review <issue-url|#123|issue text> [review focus]"
argument-hint: "<issue-url|#123|issue text> [review focus]"
model: opus
---

Issue/ref: `$1`
Focus: rest of `$ARGUMENTS` after `$1` (free-text focus hint; if empty, run all four focuses below).

Review only. No fixes unless I explicitly ask.

Flow:

1. Read the issue.
2. Inspect the current implementation / diff (`git diff`, `git log`, current branch state).
3. Dispatch parallel fresh `reviewer` subagents — one per focus, in a single message (multiple `Agent` calls in parallel):
   - correctness / regressions;
   - tests / validation;
   - simplicity / maintainability;
   - issue requirement match.
4. Synthesize their reports into:
   - **Fix now** — blocking, with `file:line` + suggested fix;
   - **Optional improve** — non-blocking, with `file:line`;
   - **Ignore / defer** — with a short why.

Every finding must cite `file:line` evidence. Drop unbacked claims.
