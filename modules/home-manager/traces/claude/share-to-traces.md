---
description: Share the current session to Traces
---

Share the current coding session to Traces by running:

```bash
traces share --cwd "$PWD" --agent claude-code --json
```

Parse the JSON output. If `ok` is `true`, reply with the `sharedUrl`.

If the trace is not found, first discover available traces:

```bash
traces share --list --cwd "$PWD" --agent claude-code --json
```

Then share a specific trace by ID:

```bash
traces share --trace-id <selected-id> --json
```

Traces route to a namespace by the folder they were created in (configured once
via `traces share config`). To override for one publish, pass an explicit
target: `traces share @<org> --trace-id <id> --json`.

Error handling:
- `AUTH_REQUIRED`: run `traces login`, then retry.
- `NEEDS_DESTINATION`: no folder rule — pass `traces share @<org> ...` or add a rule via `traces share config`.
- `TRACE_NOT_FOUND`: use `--list` to discover, then `--trace-id` to share.
- `UPLOAD_FAILED`: check network, then retry.

$ARGUMENTS
