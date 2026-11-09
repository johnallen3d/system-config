---
name: share-to-traces
description: Share the current coding session to Traces and return the share URL.
metadata:
  author: traces
  version: "1.2.0"
  cli-contract-version: "1"
  argument-hint: [optional trace id or source path]
---

# Share To Traces

Publish the active trace to Traces and return the URL.

## Triggers

- "share to traces"
- "publish this trace"
- "share this session"

## How Session Resolution Works

When this skill is triggered from a Claude Code session, the session ID is
automatically injected into the environment via the `traces-session-env.sh`
SessionStart hook. This means `traces share` will deterministically identify
the correct session.

If the hook is NOT installed, the command falls back to most-recent-trace
matching by working directory. To avoid ambiguity, use `--list` first.

## Command

### When the SessionStart hook is installed (recommended):

The hook automatically sets `TRACES_CURRENT_TRACE_ID` — just run:

```bash
traces share --cwd "$PWD" --agent claude-code --json
```

### When the hook is NOT installed (fallback with discovery):

```bash
# Step 1: List available traces
traces share --list --cwd "$PWD" --agent claude-code --json

# Step 2: Share a specific trace by ID
traces share --trace-id <selected-id> --json
```

### With explicit session hint (alternative):

```bash
TRACES_CURRENT_TRACE_ID="<session-id>" traces share --cwd "$PWD" --agent claude-code --json
```

## Destination

Each trace shares to a namespace chosen by the folder it was created in. These
folder rules are the default; the user configures them once (`traces share
config`) and every present/future subfolder inherits the nearest ancestor rule.
Do NOT guess a destination — to override for a single publish, pass an explicit
target: `traces share @<org> --trace-id <id> --json`.

## Visibility

Do NOT pass `--visibility` unless the user explicitly requests it. The CLI
defaults to the correct visibility based on the user's namespace type.

## Output Behavior

- Parse the JSON output and reply with the `sharedUrl`.
- Include which selector resolved the trace (`selectedBy`).
- On failure, use terse remediation:
  - `AUTH_REQUIRED`: run `traces login`, then retry.
  - `NEEDS_DESTINATION`: no folder rule for this directory — pass an explicit target (`traces share @<org> ...`) or add a rule with `traces share config`, then retry.
  - `NAMESPACE_CONFLICT`: the API key is bound to a different namespace than the resolved target — use a matching key or target.
  - `TRACE_NOT_FOUND`: use `traces share --list` to discover traces, then retry with `--trace-id`.
  - `INVALID_ARGUMENTS`: fix selector usage and retry.
  - `UPLOAD_FAILED`: check network/config, then retry.

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
