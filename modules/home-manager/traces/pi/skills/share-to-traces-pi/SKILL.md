---
name: share-to-traces-pi
description: Share the current Pi coding session to Traces and return the share URL. Use when running inside Pi, especially if the Traces Pi extension is installed.
metadata:
  author: traces
  version: "1.2.0"
  cli-contract-version: "1"
  argument-hint: [optional trace id or source path]
---

# Share To Traces (Pi)

Publish the active Pi trace to Traces and return the URL.

## Triggers

- "share to traces"
- "publish this trace"
- "share this session"

## How Session Resolution Works

Pi's adapter implements `getCurrentTraceHint()` which provides a heuristic
match based on most-recent trace in the current working directory. For
deterministic matching, use `--list` to discover and `--trace-id` to select.

If the Traces Pi extension is installed, it provides a `traces_share` tool
that handles session context automatically.

## Command

### Direct share (uses Pi adapter heuristic):

```bash
traces share --cwd "$PWD" --agent pi --json
```

### With discovery (recommended when multiple sessions exist):

```bash
# Step 1: List available traces
traces share --list --cwd "$PWD" --agent pi --json

# Step 2: Share a specific trace by ID
traces share --trace-id <selected-id> --json
```

## Visibility

Do NOT pass `--visibility` (or set the `visibility` tool parameter) unless the
user explicitly requests it. The CLI defaults to the correct visibility based
on the user's namespace type.

## Output Behavior

- Parse the JSON output and reply with the `sharedUrl`.
- On failure:
  - `AUTH_REQUIRED`: run `traces login`, then retry.
  - `TRACE_NOT_FOUND`: use `--list` to discover, then `--trace-id`.
  - `UPLOAD_FAILED`: check network, then retry.

## Historical sharing

Trigger: “share all my traces”.

When the user asks to share historical traces:

1. Run `traces share status --unshared --json` for the requested directory or roots.
2. If any relevant branch reports `No destination`, run `traces share config` and show the complete current map. Ask the user to choose each destination or `Don't share`; ask for confirmation before changing any rule, and preserve every existing rule when writing the full map with `traces share config --set`.
3. After a confirmed configuration change, rerun `traces share status --unshared --json` and do not upload until the scope is verified.
4. For each verified absolute filesystem root, run one command at a time: `traces share upload --dir <absolute-root> --json`.
5. Report deliberate `Don't share` opt-outs, every successful share URL, and every failure. A partial runtime failure may be retried; prior remote successes are skipped by default.

Safety rules:
- Never guess a namespace or silently change the active namespace.
- Never transfer a trace automatically; ask before any transfer or routing change.
- If upload preflight fails, stop and explain the issue; do not continue with another root.
- Keep the existing single-session sharing workflow unchanged for requests such as `share to traces` or `publish this trace`.
