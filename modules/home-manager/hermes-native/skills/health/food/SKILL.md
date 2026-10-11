---
name: food
description: Log or adjust food in the Personal vault.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Nutrition, Daily Note]
    related_skills: [personal-daily-operations]
---
# Food Log Skill

Interpret the complete instruction supplied with `/food`, then make one verified
nutrition change in the Personal vault. Use the existing deterministic writers;
do not invoke Pi or the workstation-only `log-food` wrapper.

## When to Use

- Use for normal food logging, planned meals, and corrections to existing meals.
- Preserve every supplied word while interpreting quoted text, quantities, and
  relative date or time phrases.
- Do not use for general nutrition advice that does not request a vault change.

## Prerequisites

- `VAULT_DIR`, `VLT_VAULT_PATH`, and `VLT_VAULT` identify the mounted Personal
  vault.
- Run commands from `$VAULT_DIR` with the `terminal` tool.
- The deterministic vault tasks and `vlt` must be available.

## Procedure

1. If the instruction is empty or the meal, amount, food identity, or date is
   missing, ask one focused follow-up and do not write. If only nutrition data
   is unavailable, use a transparent best-effort estimate instead of asking.
2. Run `date '+%Y-%m-%d %H:%M:%S %Z (%z)'`. Resolve relative language from that
   value, never from the conversation timestamp.
3. Read the target daily note with
   `vlt vault="Personal" read file="journal/PATH.md"` before any correction.
4. Resolve food locally first with `mise run common-food -- search QUERY`,
   `mise run common-food -- show FOOD_ID`, and recipe notes read through the
   fixed `vlt` read route. Native production does not expose an arbitrary
   `scripts/food-pick` or workstation shell fallback. Preserve the
   supplied serving description; do not invent a portion. When the local vault
   has no defensible match, use a reputable external source for a best-effort
   nutrition estimate, record the assumptions and source URL, and report it as
   an estimate. External lookups remain unavailable in offline native staging.
5. For a normal entry, call `mise run write-food-log --` with normalized meal,
   food ID, amount, unit, all five nutrition values, resolved date/time, and
   source. Never call `mise run log-food`.
6. For an adjustment, identify exactly one existing structured meal entry. If
   none or more than one matches, ask a focused follow-up. Run the skill-relative
   `scripts/adjust-food-log` with `--date`, `--meal`, optional `--match-food`, and
   the complete normalized replacement payload. This helper replaces one line,
   recomputes totals, locks the note, writes atomically, and is retry-safe.
7. Read the target note back through `vlt`. Verify the intended entry occurs
   exactly once, the replaced entry is absent, totals match all structured
   nutrition entries, and no unrelated content changed.
8. Reply briefly with the meal, date, what changed, and verification result.

## Quick Reference

```bash
mise run write-food-log -- --meal lunch --food FOOD_ID --label "LABEL" \
  --amount AMOUNT --unit "UNIT" --calories CALORIES \
  --protein-g PROTEIN --carbs-g CARBS --fat-g FAT --fiber-g FIBER \
  --date YYYY-MM-DD --time HH:MM --source common

SKILL_DIR/scripts/adjust-food-log --date YYYY-MM-DD --meal dinner \
  --match-food OLD_FOOD_ID --food NEW_FOOD_ID --label "LABEL" \
  --amount AMOUNT --unit "UNIT" --calories CALORIES \
  --protein-g PROTEIN --carbs-g CARBS --fat-g FAT --fiber-g FIBER \
  --source recipe
```

Resolve `SKILL_DIR` to the directory containing this `SKILL.md`; never type the
placeholder literally.

## Pitfalls

- Do not append a replacement beside the old meal.
- Do not edit a daily note with shell redirection, `sed`, or an unlocked script.
- Do not run concurrent writers against the same daily note.
- Do not treat an exact duplicate or retry as a second meal.
- Do not write when the meal, amount, food identity, or date is missing. If
  nutrition is unavailable, proceed with a transparent best-effort estimate and
  label the source and assumptions.
- Native staging does not expose a terminal writer or production vault. This
  policy document and disposable checks do not grant real-vault write authority.

## Verification

A successful operation has one intended structured entry, correct computed
Daily Totals, successful `vlt` readback, and no change outside the target note.
