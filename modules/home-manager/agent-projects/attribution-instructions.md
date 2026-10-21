
## Implementation attribution

- Before staging or committing, read the Nix-managed
  `~/.agents/skills/authoring-commits/SKILL.md`. It is the canonical commit skill
  for personal and work Pi/Claude profiles; prefer it over packaged versions
  with the same name. Keep all existing authorization and project-specific gates.
- `Co-Authored-By` credits models that materially authored the scoped code, tests,
  documentation, or configuration, not the model currently running cleanup.
  This user-level policy overrides packaged skills' current-model or
  self-identity rules, commit-message-only co-authorship, and Claude Code's
  current-model attribution reminders.
- Keep cheaper cleanup models (including personal `/wrap`). Validation, commit-message drafting, Git/tracker
  operations, integration, and worktree cleanup alone do not earn co-authorship.
  If the cleanup model also makes substantive changes, credit it alongside the
  implementers; never replace their credit. Preserve existing legitimate trailers
  and the user's Git author identity. Do not amend historical commits without
  separate authorization.
- During implementation, maintain an attribution handoff in the conversation,
  and include it in the implementation completion/checkpoint summary before
  cleanup or compaction. Record the task branch/worktree, each substantive
  contributor's tool/provider/model, what scoped paths it authored, and the
  supporting session/message or delegated-result evidence. No new tracked file
  is needed. Include substantive delegated contributors, not just the parent.
- Verify identities using harness/session metadata for the actual work-phase
  assistant messages and successful scoped write/edit operations, including reviewed
  shell writes. Self-identification in prose, the selected/default model, the
  last model before `/wrap`, and an attribution reminder are not proof of who
  implemented the change. Use recent commits only for the established trailer
  email/format convention, never to infer contributor models or invent emails.
- Before committing, including in personal `/wrap`, recover and verify the
  implementation attribution handoff against the scoped change and work-phase
  evidence, then retain those
  contributor identities across the cleanup model switch. If the handoff is
  missing or incomplete, inspect the original task session/tool metadata and
  relevant delegated handoffs; do not scan unrelated profiles or choose the
  newest session by timestamp. In Pi, `runtime_model_info` exposes the current
  session file, but its current model is not implementation provenance. In
  Claude, use the current task transcript's assistant `message.model` fields,
  not its generated attribution reminder. Record the resolved contributors and
  evidence in the conversation before creating the commit. Use one trailer per
  verified substantive contributor, deduplicating identical identities.
- If contributor identity, task scope, delegated provenance, or the trailer email
  convention cannot be verified, stop before committing and ask one targeted
  question. Do not fall back to the cleanup model or silently omit attribution.
  A missing handoff never authorizes a guess. This is instruction-level policy,
  not a harness-enforced authorship tracker.
