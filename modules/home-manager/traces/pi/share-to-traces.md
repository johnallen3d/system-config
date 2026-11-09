---
description: Share the current session to Traces
---

Share the current coding session to Traces by running:

```bash
traces share --cwd "$PWD" --agent pi --json
```

Parse the JSON output. If `ok` is `true`, reply with the `sharedUrl`.

If the trace is not found, first discover available traces:

```bash
traces share --list --cwd "$PWD" --agent pi --json
```

Then share a specific trace by ID:

```bash
traces share --trace-id <selected-id> --json
```

Error handling:
- `AUTH_REQUIRED`: run `traces login`, then retry.
- `TRACE_NOT_FOUND`: use `--list` to discover, then `--trace-id` to share.
- `UPLOAD_FAILED`: check network, then retry.
