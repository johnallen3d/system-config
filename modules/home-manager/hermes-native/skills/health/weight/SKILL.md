---
name: weight
description: Log body weight in the Personal vault.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Weight, Daily Note]
    related_skills: [personal-daily-operations]
---
# Weight Log Skill

Interpret the complete instruction supplied with `/weight` and route one
verified value through the deterministic Personal-vault weight writer. Do not
invoke Pi or perform a free-form vault edit.

## When to Use

- Use when the user asks to log body weight.
- Preserve the supplied value, units, and date context.
- Do not use for weight analysis or advice without a logging request.

## Prerequisites

- `VAULT_DIR`, `VLT_VAULT_PATH`, and `VLT_VAULT` identify the mounted Personal
  vault.
- Run commands from `$VAULT_DIR` with the `terminal` tool.
- `mise run log-weight` and `vlt` must be available.

## Procedure

1. If the instruction has no unambiguous numeric weight, ask one focused
   follow-up and do not write.
2. Run `date '+%Y-%m-%d %H:%M:%S %Z (%z)'`. The current deterministic writer
   supports today's note only. If the request resolves to another date, explain
   that limitation and ask for confirmation rather than writing to today.
3. Normalize pounds to a plain numeric value. If another unit is supplied,
   request pounds unless the conversion is explicit and unambiguous.
4. Run `mise run log-weight -- VALUE` exactly once.
5. Read today's daily note through `vlt vault="Personal" read` and verify exactly
   one `weight:: VALUE` field. Treat a duplicate/retry as success only when the
   stored value already matches.
6. Reply briefly with the value, date, and verification result.

## Quick Reference

```bash
mise run log-weight -- VALUE
```

## Pitfalls

- Do not guess a missing value or unit.
- Do not write a historical request into today's note.
- Do not invoke `log-weight` twice after a delayed response.
- Do not edit weight metadata with shell redirection or an unlocked script.

## Verification

A successful operation has exactly one matching weight field in today's daily
note and successful `vlt` readback.
