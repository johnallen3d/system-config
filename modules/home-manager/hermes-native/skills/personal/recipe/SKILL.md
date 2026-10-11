---
name: recipe
description: Create, import, update, scale, or answer questions about Personal-vault recipes.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Recipe, Nutrition, Common Foods]
    related_skills: [food, food-label]
---
# Recipe Workflow Skill

Handle the complete `/recipe` request directly in the mounted Personal vault.
Preserve URLs, adjustments, scaling details, substitutions, and date context.
Do not invoke Pi or the workstation-only `log-recipe` wrapper.

## Procedure

1. Identify the intent: import from a supplied URL, create a recipe, update an
   existing recipe, scale or substitute ingredients, maintain reusable
   nutrition, or answer a recipe-specific vault question. Ask one focused
   follow-up only when the request cannot be completed responsibly.
2. Read `health/food-dislikes.md`, relevant nearby files under `recipes/`, and
   any matching entry in `health/common-foods.yaml`. Use local vault data by
   default. If the user supplied a recipe URL, fetch that URL and directly
   linked content needed for the recipe; otherwise ask before web research.
3. Read before writing with `vlt vault=Personal read file=recipes/NAME.md`.
   Native production does not expose generic `vlt` mutations or shell writes.
   Create/update through the single guarded command
   `mise run save-recipe -- recipes/NAME.md MARKDOWN_JSON PLAN_JSON`, with each
   JSON argument individually shell-quoted as one literal argument. The second
   argument is a JSON string (encode newlines as `\n`, not literal command
   newlines). The third is an explicit renderer plan object. Follow nearby
   naming/structure and include the complete intended canonical Markdown.
4. Preserve canonical `## Ingredients` and `## Steps`/`## Instructions`/`## Method`
   sections. Do not add microwave reheating instructions unless requested.
5. Supply the existing renderer's plan: `row_order` contains every ingredient's
   zero-based index exactly once; `columns` contains 1–8 objects with `label`
   and `cells`. Each cell has inclusive `start`/`end` positions in `row_order`,
   `title`, optional `detail`, and one-based source `steps`. Every step must
   appear, and cells within a column cannot overlap. The guarded adapter runs
   the existing deterministic renderer with this private plan, validates it,
   and commits/readbacks only the canonical recipe postimage. Never hand-write
   generated HTML, invoke Pi, or fall back to an implicit planner. A renderer
   failure retains the private candidate and leaves the actual note unchanged.
6. Include yield, serving size, and per-serving nutrition when supplied or
   responsibly estimable. State material assumptions. When nutrition is
   defensible, create or update a stable matching entry in
   `health/common-foods.yaml` with aliases, recipe path, nutrition, and notes.
   Do not invent nutrition when inputs are insufficient.
7. For reusable foods, use `mise run save-common-food -- FOOD_JSON` with one
   shell-quoted JSON object: stable lowercase `id`, `name`, explicit positive
   `serving.amount`/`serving.unit`, and finite nonnegative `nutrition.calories`,
   `protein_g`, `carbs_g`, `fat_g`. Optional aliases/category/recipe/notes/source,
   serving label, fiber/sugar/sodium are literal metadata. Disclose estimates
   in notes/source. The adapter upserts by exact ID in `health/common-foods.yaml`,
   preserves other entries/metadata, validates, regenerates the existing browser,
   and commits/readbacks exactly those two files. It never creates per-food
   Markdown or changes daily meal logs. No generic YAML write is available.
8. Verify Markdown changes with `vlt vault="Personal" read` and ensure the
   intended recipe appears exactly once without unrelated changes.
9. If the request is actually a daily meal-log request, follow the managed food
   workflow and its deterministic `write-food-log` authority rather than
   treating it as a recipe edit.
10. Reply briefly with what changed or what you concluded and any material
    assumption.

## Pitfalls

- Do not call `mise run log-recipe`; it starts a one-off Pi session and is
  unavailable in Hermes.
- Do not hand-edit generated recipe-table HTML.
- Do not use unlocked shell redirection, `sed -i`, or concurrent writers on one
  vault file.
- Do not turn a reusable recipe request into a meal log.

## Verification

A successful mutation has a verified canonical recipe note, regenerated table
when applicable, valid reusable nutrition when applicable, and no unrelated
vault changes.
