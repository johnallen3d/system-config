---
name: task
description: Capture one task in the appropriate Personal-vault list.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Tasks, Lists, Daily Note]
---
# Task Capture Skill

Interpret the complete `/task` instruction and capture exactly one item through
the deterministic Personal-vault list writer.

## List Selection

- Shopping or non-food store items: `shopping`
- Food or ingredients: `groceries`
- Journal or daily-note actions: `daily`
- Everything else: `tasks`

Honor an explicit user-selected list over inference.

## Procedure

1. If no actionable item is present, ask one focused follow-up and do not write.
2. Preserve the item wording. Run `date '+%Y-%m-%d %H:%M:%S %Z (%z)'` and
   resolve any relative due date or time from that value. Normalize a resolved
   date to `YYYY-MM-DD` and time to `HH:MM`; do not add either when none was
   requested or implied.
3. Infer exactly one list using the rules above.
4. From `$VAULT_DIR`, run one argv-safe command:

   ```bash
   mise run add-list-item -- "COMPLETE_ITEM" LIST
   ```

   Append `--date YYYY-MM-DD` and `--time HH:MM` only when resolved. Keep the
   complete item as one quoted argument. Never invoke the writer twice after a
   delayed response.
5. Read back the reported target through `vlt vault="Personal" read` and verify
   the task appears exactly once with the expected list and due metadata.
6. Reply briefly with the item and destination.

## Pitfalls

- Do not split one request across several lists.
- Do not guess a materially ambiguous item, list, date, or time.
- Do not edit list files directly; `add-list-item` is the write authority and
  provides locking and duplicate protection.
- Do not use the Obsidian application CLI for verification.

## Verification

A successful capture has exactly one matching task in one intended list and a
successful `vlt` readback.
