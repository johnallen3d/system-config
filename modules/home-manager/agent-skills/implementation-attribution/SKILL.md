---
name: implementation-attribution
description: Use before any personal git commit (including /wrap) to decide Co-Authored-By trailers, and when writing an implementation completion or checkpoint summary.
---

# Implementation attribution

`Co-Authored-By` credits models that materially authored the scoped code, tests,
docs, or configuration, not the model running cleanup. This overrides packaged
skills' current-model rules and Claude Code's attribution reminders.

## What earns credit

- Validation, commit-message drafting, Git/tracker operations, integration, and
  worktree cleanup alone do not. A cleanup model that also makes substantive
  changes is credited alongside the implementers, never instead of them.
- Include substantive delegated contributors, not just the parent.
- Preserve existing legitimate trailers and John's Git author identity. Never
  amend historical commits without separate authorization.

## Handoff during implementation

Keep an attribution handoff in the conversation and include it in the completion
or checkpoint summary before cleanup or compaction: task branch/worktree, each
contributor's tool/provider/model, the scoped paths it authored, and the
session/message or delegated-result evidence. No tracked file is needed.

## Verifying before commit

- Recover the handoff and check it against the scoped change and work-phase
  evidence; retain those identities across a cleanup model switch.
- Evidence is harness/session metadata for the work-phase assistant messages and
  successful scoped writes/edits (including reviewed shell writes). In Claude,
  use the task transcript's assistant `message.model` fields; in Pi,
  `runtime_model_info` locates the session file but its current model is not
  provenance; in Antigravity (`agy`), use the task transcript's
  `PLANNER_RESPONSE` `.model` fields paired with its `tool_calls`. Prose
  self-identification, the selected/default model, `<USER_SETTINGS_CHANGE>` /
  `Model Selection`, the last model before `/wrap`, and attribution reminders
  are not proof.
- Claude transcripts are readable JSONL under
  `$CLAUDE_CONFIG_DIR/projects/<slug>/<session-id>.jsonl`, where `<slug>` is
  the session's start directory with `/` and `.` replaced by `-` (often the
  primary checkout, not the worktree). Never claim they are unreadable. Find the
  task session by its task branch/worktree name, and the model behind each
  scoped write with:

  ```bash
  dir="$CLAUDE_CONFIG_DIR/projects"
  grep -rl --include='*.jsonl' "$branch_or_worktree" "$dir"/-<repo-slug>*
  jq -r 'select(.type=="assistant") | .message.model as $m
    | .message.content[]? | select(.type=="tool_use")
    | "\($m)\t\(.name)\t\((.input.file_path // .input.command // "")|tostring|.[0:120])"' \
    -- "$transcript"
  ```

- Antigravity (`agy`) transcripts are readable JSONL under
  `~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript_full.jsonl`
  (prefer `transcript_full.jsonl` over `transcript.jsonl`, which may truncate
  `tool_calls`). Use `Conversation ID` from `<user_information>` in the active
  session, or locate another task's session by branch/worktree, and list the
  model behind each scoped write with:

  ```bash
  grep -rl "$branch_or_worktree" ~/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript.jsonl
  jq -r 'select(.type=="PLANNER_RESPONSE") | .model as $m
    | .tool_calls[]?
    | "\($m)\t\(.name)\t\((.args.Path // .args.CommandLine // "")|tostring|.[0:120])"' \
    -- "$transcript_full"
  ```

  Models seen only on reads, skill lookups, or Git/tracker steps earn no
  credit. Resolve attribution from this output yourself; ask John only if the
  transcript is missing or the writes themselves are ambiguous.
- If the handoff is missing, inspect the original task session and delegated
  handoffs only; never scan unrelated profiles or pick the newest session.

## Trailer conventions

If the repository already establishes a `Co-Authored-By:` format for a
contributor's provider, match it. Otherwise — including when a repository has no
prior commits from that provider — use these established personal defaults
without stopping to ask John:

- **Antigravity / Gemini** (`agy`, or Gemini models via Antigravity in Pi/Claude):
  `Co-Authored-By: Antigravity (<Model>) <noreply@google.com>` — e.g.
  `Co-Authored-By: Antigravity (Gemini 4 Neon) <noreply@google.com>`,
  `Co-Authored-By: Antigravity (Gemini 4 Hydrogen) <noreply@google.com>`,
  `Co-Authored-By: Antigravity (Gemini 4 Argon) <noreply@google.com>`,
  `Co-Authored-By: Antigravity (Gemini 3.8 Flash) <noreply@google.com>`.
  Map model IDs to human-readable names and drop proxy effort suffixes
  (`-xhigh`, `-high`, `-low`), e.g. `gemini-4-neon` or `gemini-4-neon-xhigh` →
  `Gemini 4 Neon`.
- **Claude** (including Claude models run in `agy` or via Antigravity):
  `Co-Authored-By: Claude <Model> <noreply@anthropic.com>` — e.g.
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (drop proxy effort
  suffixes such as `claude-opus-5-5-high` → `Claude Opus 5.5`).
- **OpenAI / Codex**:
  `Co-Authored-By: OpenAI Codex (<model-id>) <noreply@openai.com>` — e.g.
  `Co-Authored-By: OpenAI Codex (gpt-6.1-sol) <noreply@openai.com>`.

Use recent commits only to check for a repo-specific format convention, never to
infer contributor models or invent emails for an unlisted provider.

## Final check

- Record the resolved contributors and evidence in the conversation, then write
  one trailer per verified contributor, deduplicated.
- Stop before committing and ask one targeted question only if contributor
  identity, scope, or delegated provenance can't be verified, or if an unlisted
  provider has neither a documented default above nor a repo convention. Never
  fall back to the cleanup model or silently omit attribution.
