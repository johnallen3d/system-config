---
description: "Implement from issue. Usage: /implement <issue-id|#123|bd-id> [extra bullet instructions]"
argument-hint: "<issue-id|#123|bd-id> [extra bullet instructions]"
model: opus
---

- Read issue `$1`.

Rest of `$ARGUMENTS` (after `$1`) is extra bullet instructions to factor into the plan.

- Invoke the `issue-driven-implementation` skill and follow it all the way to PR creation.
