---
name: video
description: Capture YouTube notes and a full transcript into today's Personal daily note.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, YouTube, NotebookLM, Daily Note]
---
# YouTube Video Capture Skill

Handle the complete `/video` request directly with the mounted Personal vault
and the configured NotebookLM workflow. Preserve the YouTube URL and optional
focus question. Do not invoke Pi or the workstation-only `log-video` wrapper.

## Procedure

1. Run `date '+%Y-%m-%d %H:%M:%S %Z (%z)'` to establish today's local date.
   Parse the first YouTube URL from the complete instruction; all remaining text
   is the optional focus. If a valid YouTube URL is missing, ask for one and do
   not write.
2. From `$VAULT_DIR`, add the URL as a YouTube source with
   `mise run nlm -- source add URL --type youtube --json`. Parse and retain its
   source ID; do not guess it from human-readable output.
3. Wait for processing with
   `mise run nlm -- source wait SOURCE_ID --timeout 300`. On failure or timeout,
   report it without changing the vault.
4. Create a unique temporary Markdown path under `/tmp`. Retrieve the complete
   transcript with
   `mise run nlm -- source fulltext SOURCE_ID --format markdown -o TEMP_PATH`,
   then read that file. Do not use transcript text printed to stdout because it
   can be truncated.
5. Ask NotebookLM only about this source with
   `mise run nlm -- ask --source SOURCE_ID ...`. Request detailed Markdown with
   a concise summary, key points, concrete facts/names/numbers, actionable
   takeaways, timestamped sections when available, preserved citations, and an
   answer to the optional focus.
6. Resolve today's `journal/YYYY-MM-DD.md`. Read it with
   `vlt vault="Personal" read`. If missing, source
   `.mise/tasks/lib-vlt-note.sh` and call `ensure_daily_exists` for that exact
   path; never use `vlt daily`.
7. Build one section headed `## Video Notes`, followed by
   `### [VIDEO_TITLE](URL)`, the NotebookLM notes, and a collapsible
   `<details><summary>Transcript</summary>` block containing the complete
   transcript. If `## Video Notes` already exists, append under it rather than
   creating another same-level section.
8. Hold the daily note's external workflow lock and use the flocked atomic
   read-modify-write pattern from `.mise/tasks/lib-vlt-note.sh`. Before writing,
   check for the same URL and do not append a duplicate on retry. Do not use
   shell redirection or `sed -i` against the note.
9. Read the daily note back through `vlt` and verify the URL and complete
   transcript block occur exactly once. Remove the temporary transcript file.
10. Reply briefly with the video title and daily-note path.

## Pitfalls

- Do not call `mise run log-video`; it starts a one-off Pi session and is
  unavailable in Hermes.
- Do not use an unrestricted NotebookLM answer when `--source SOURCE_ID` can
  constrain it.
- Do not write a partial capture when source processing or full-transcript
  retrieval fails.
- Do not expose NotebookLM authentication state or diagnostics in the reply.

## Verification

A successful capture has one linked video section, source-grounded notes, the
full transcript in today's note, clean temporary state, and no unrelated vault
changes.
