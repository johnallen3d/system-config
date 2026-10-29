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
  provenance. Prose self-identification, the selected/default model, the last
  model before `/wrap`, and attribution reminders are not proof.
- If the handoff is missing, inspect the original task session and delegated
  handoffs only; never scan unrelated profiles or pick the newest session.
- Use recent commits only for the trailer email/format convention, never to infer
  contributors or invent emails.
- Record the resolved contributors and evidence in the conversation, then write
  one trailer per verified contributor, deduplicated.
- If identity, scope, delegated provenance, or the email convention can't be
  verified, stop before committing and ask one targeted question. Never fall back
  to the cleanup model or silently omit attribution.
