---
name: food-label
description: Import food-package or nutrition-label photos into reusable common foods.
version: 0.1.0
author: John Allen, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Personal, Nutrition, OCR, Common Foods]
    related_skills: [food, recipe]
---
# Food Label Import Skill

Interpret `/food-label` as reusable food-data capture, not as a meal log. Work in
the mounted Personal vault with the images delivered in the current request. Do
not invoke Pi or the workstation-only `import-food-label` wrapper.

## Procedure

1. Preserve the complete command text and inspect the current request's native
   image attachments. Resolve every attachment to its exact local path. If no
   image is available, ask for a clear package front and Nutrition Facts panel
   and do not write.
2. Inspect the supplied package images with native image vision. The native
   controller does not expose `ocr-label`, arbitrary image-path reads, or an
   alternate OCR subprocess: do not invoke or claim those capabilities. If the
   current request's visible text is ambiguous, ask for a clearer image or an
   explicit transcription instead of guessing.
3. Combine complementary images of one package. Treat images of distinct
   products as separate foods. The visible package and OCR text are the only
   authority for identity, serving size, calories, protein, carbohydrates, fat,
   fiber, and other package values.
4. If the Nutrition Facts panel is absent, cropped, or unreadable, report
   exactly which required fields are unavailable and ask for a clearer image.
   Never substitute generic nutrition values or create a partial entry.
5. Unless the user explicitly requested read-only validation, read the canonical
   `health/common-foods.yaml` with `vlt vault=Personal read file=health/common-foods.yaml`.
   Prepare one bounded JSON object with a stable
   lowercase kebab-case `id`, literal `name`, optional aliases/category, a
   `serving` object with positive `amount` and explicit `unit`, and `nutrition`
   containing finite nonnegative `calories`, `protein_g`, `carbs_g`, and `fat_g`.
   Optional nutrition fields are `fiber_g`, `sodium_mg`, and `sugar_g`. Put the
   package-photo source and transparent division/rounding in `notes` or `source`.
6. Invoke `mise run save-common-food -- FOOD_JSON` with the complete JSON object
   as one individually shell-quoted argument. This fixed guarded adapter upserts
   by exact ID, preserves unrelated records/metadata, validates the private YAML,
   renders the browser, and commits only `health/common-foods.yaml` and
   `health/common-foods-browser.html` with shared locking, preimages, atomic CAS,
   exact readback and Syncthing convergence. Do not use generic vlt writes,
   redirects, filesystem edits, or per-food Markdown.
7. Require the adapter's successful completion; on refusal, stop and report it.
   Never claim success from a separate validation command or retry an uncertain
   write. Read-only validation may use `mise run common-food -- validate` without
   running the writer or browser generator.
8. Reply briefly with the imported food or foods and any material assumptions.
   Do not also create a daily meal entry.

## Pitfalls

- Do not call `mise run import-food-label`; it starts a one-off Pi session and
  is unavailable in Hermes.
- Do not infer package nutrition from product familiarity.
- Do not silently use an earlier conversational image when the current request
  has no attachment.
- Do not mutate the vault during an explicit read-only or validation request.

## Verification

A successful import has visible/OCR-grounded per-serving values, a valid common
food entry, a rebuilt browser, and no meal-log or unrelated vault changes.
