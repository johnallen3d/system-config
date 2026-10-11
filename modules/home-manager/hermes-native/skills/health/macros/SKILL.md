---
name: macros
description: Report aggregate or meal-level nutrition macros from the Personal vault.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Nutrition, Daily Note]
    related_skills: [food, personal-daily-operations]
---
# Daily Macros Skill

Report the deterministic nutrition summary requested with `/macros`. This is a
read-only operation. Do not estimate nutrition, edit the vault, or invoke Pi.

## Procedure

1. Preserve the complete optional date and meal arguments. If no date is
   supplied, use today's date in `America/New_York`.
2. Run from `$VAULT_DIR`:
   - no arguments: `mise run macros`
   - date only: `mise run macros -- DATE`
   - meal only: `mise run macros-details -- --meal MEAL`
   - date and meal: `mise run macros-details -- --date DATE --meal MEAL`
   Use the option forms for meal reports so a multi-word meal remains one
   argument.
3. Reply with the command output exactly as printed, preserving every line
   break. Do not wrap it in a paragraph or code fence.
4. If the date or meal is ambiguous or the task fails, ask one focused
   follow-up or report the failure; never substitute a different date or meal.

## Verification

The commands must remain read-only. Aggregate output must come directly from
the vault's deterministic `macros` task, and itemized output must come directly
from its deterministic `macros-details` task.
