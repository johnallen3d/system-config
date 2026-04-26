---
description: "Wrap up the session: close issues, commit. Optional commit message: /wrap <message>"
model: gpt-5.4-mini
skill: wrapping-up
subagent: delegate
---

Follow the wrapping-up skill workflow.

Commit message: if "$@" is non-empty, use it verbatim. Otherwise derive one from the changes and work done this session.
