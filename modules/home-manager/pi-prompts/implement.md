---
description: "Implement from issue. Usage: /implement <issue-id|#123|bd-id> [extra bullet instructions]"
model: gpt-5.6-terra
subagent: delegate
---

- read issue $1

${@:2}

- load and follow `issue-driven-implementation` skill all the way to PR creation
