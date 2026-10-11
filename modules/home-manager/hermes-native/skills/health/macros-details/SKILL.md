---
name: macros-details
description: Report itemized nutrition macros for today or a requested date and meal from the Personal vault.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Nutrition, Daily Note]
    related_skills: [macros, food, personal-daily-operations]
---
# Detailed Daily Macros Skill

Report the deterministic itemized nutrition summary requested with
`/macros-details`. This is a read-only operation. Do not estimate nutrition,
edit the vault, or invoke Pi.

## Procedure

1. Preserve the complete optional date and meal arguments. If no date is
   supplied, use today's date in `America/New_York`.
2. Run from `$VAULT_DIR`, using the option forms when values are present so a
   multi-word meal remains one argument:
   - no arguments: `mise run macros-details`
   - date only: `mise run macros-details -- --date DATE`
   - meal only: `mise run macros-details -- --meal MEAL`
   - date and meal: `mise run macros-details -- --date DATE --meal MEAL`
3. Reply with the command output exactly as printed, preserving every line
   break. Do not wrap it in a paragraph or code fence.
4. If the date or meal is ambiguous or the task fails, ask one focused
   follow-up or report the failure; never substitute a different date or meal.

## Verification

The command must remain read-only and its output must come directly from the
vault's deterministic `macros-details` task. Telegram publishes this hyphenated
skill as the menu-safe `/macros_details` alias.
