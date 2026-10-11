---
name: activity
description: Log physical activity in the Personal vault.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Activity, Daily Note]
    related_skills: [personal-daily-operations]
---
# Activity Log Skill

Interpret the complete instruction supplied with `/activity` and route one
verified entry through the deterministic Personal-vault activity writer. Do not
invoke Pi or the workstation-only `log-activity` wrapper.

## When to Use

- Use when the user asks to log physical activity or exercise.
- Preserve the full activity text, including date, time, duration, distance,
  speed, incline, punctuation, and quoted text.
- Do not use for general exercise advice without a logging request.

## Prerequisites

- `VAULT_DIR`, `VLT_VAULT_PATH`, and `VLT_VAULT` identify the mounted Personal
  vault.
- Run commands from `$VAULT_DIR` with the `terminal` tool.
- `mise run activity-log` and `vlt` must be available.

## Procedure

1. If the instruction is empty or the activity itself is missing, ask one
   focused follow-up and do not write.
2. Run `date '+%Y-%m-%d %H:%M:%S %Z (%z)'` and resolve relative date/time
   language from that value.
3. Preserve the user's activity description without dropping any measurements.
   Normalize only the resolved date to `YYYY-MM-DD` and time to `HH:MM`.
4. Run `mise run activity-log --`, adding `--date` and `--time` when resolved,
   followed by the complete activity description as one quoted argument. Never
   call `mise run log-activity`.
5. Read the target note through `vlt vault="Personal" read` and verify the raw
   activity text and parsed structured fields. Treat a duplicate/retry result as
   success only when exactly one matching entry exists.
6. Reply briefly with the activity, date/time, and verification result.

## Quick Reference

```bash
mise run activity-log -- --date YYYY-MM-DD --time HH:MM \
  "complete activity text"
```

## Pitfalls

- Do not guess an omitted activity, date, or materially ambiguous measurement.
- Do not split the description into shell words or discard quoted text.
- Do not run concurrent writers against the same daily note.
- Do not append a second entry after an exact duplicate/retry response.

## Verification

A successful operation has exactly one matching raw activity entry in the
resolved daily note and the expected parsed duration, speed, incline, distance,
and calorie fields when those values were supplied or derivable.
