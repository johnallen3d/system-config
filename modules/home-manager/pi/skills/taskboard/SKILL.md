---
name: taskboard
description: Create and maintain a lightweight live Markdown task board for an AI session. Use when the user asks for /taskboard, a sticky task list, a side-pane plan, a visible progress tracker, or a harness-agnostic board that works across repositories and terminals.
---

# Taskboard

Keep session work visible in one plain `TASKS.md`. Use the bundled CLI for deterministic lifecycle operations; edit the Markdown directly when a change is richer than a status transition.

## Start

Run:

```sh
node <skill-dir>/scripts/taskboard.mjs start --side --title "<short session title>" --owner "<harness or person>" \
  "<first task>" "<second task>"
```

When the user says `start taskboard`, always pass `--side`. Use `--bottom` only when the user asks for it, or `--no-pane` for file-only mode. Outside Supacode, creation still succeeds and prints the board path.

After starting, verify the exact result and tell the user where the board lives and whether the live pane opened. Never guess or say `likely`. On this setup, live panes should prefer the `glow-watch` fish function when available; otherwise the bundled plain-text watcher is fine.

## Maintain

Update the board whenever the working plan materially changes, not for every command:

```sh
taskboard add --owner Codex "Verify the release"
taskboard doing T2
taskboard done T1
taskboard block T3 "waiting for credentials"
taskboard reopen T3
taskboard show
```

If `taskboard` is not installed, replace it with `node <skill-dir>/scripts/taskboard.mjs`.

Use these states consistently:

- `[ ]` queued
- `[~]` active
- `[x]` complete
- `[🔒]` blocked; include the concrete blocker

Keep task IDs stable. Prefer one active task. Preserve useful user edits and notes in `TASKS.md`.

Group tasks into stable owner lanes using `### <owner>` headings under `## Tasks`.
Pass `--owner` to `start` or `add`; use `TASKBOARD_OWNER` as the session default.
The CLI refreshes the board-level ISO timestamp on every task mutation. Move a
task between owner lanes by editing only its whole task line; do not change its ID.

## Display lifecycle

- `taskboard open --side` or `taskboard open --bottom`: open the live Supacode view. Prefer the `glow-watch` preview path when the local fish function exists.
- `taskboard close`: close only the tracked pane and retain the board.
- `taskboard close --remove`: close the pane and delete this session's board/state.
- `taskboard path`: print the Markdown path for handoff or manual viewing.

The CLI captures the created pane UUID and persists the originating worktree, tab, and surface IDs. Never substitute ambient Supacode IDs when closing a tracked pane.

## Guardrails

- Store session state outside the repository by default so task tracking does not dirty the worktree.
- Do not overwrite an existing board. Continue it, or use a distinct `TASKBOARD_SESSION`/`--state-dir`.
- Re-read the board before every update because multiple harnesses may share it.
- Do not mark work complete until its verification evidence exists.
- On every normal session exit, run `taskboard close` to close the tracked pane and retain the board.
- Ask before `taskboard close --remove` if the board may still be useful as a handoff.
