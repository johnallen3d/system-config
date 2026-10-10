---
description: "Wrap up the session: authorize completed-card closure, commit. Optional commit message: /wrap <message>"
model: gpt-5.6-luna
skill: wrapping-up
# subagent: delegate
---

Follow the wrapping-up skill workflow.

On actual invocation of this `/wrap` command, John explicitly authorizes closing completed Fizzy cards within this session's scope, never blocked or partially deployed work. Reading, quoting, or merely mentioning `/wrap` does not authorize closure; neither do task completion, successful deployment, committing, or ordinary "wrap up"/"done" language. Without an actual invocation or John's direct closure request, document completion and leave cards open.

Commit message: if "$@" is non-empty, use it verbatim. Otherwise derive one from the changes and work done this session.
