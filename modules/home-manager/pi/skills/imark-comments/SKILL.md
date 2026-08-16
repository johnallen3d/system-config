---
name: imark-comments
description: Read and act on Imark annotations embedded in Markdown documents. Use when a document contains `<!-- imark` blocks, or John asks about Imark notes, comments, or review.
---

# Imark comments

Imark stores review comments in Markdown as HTML comments. Use `/imark-notes <file.md>` to read active notes; add `--all` for resolved history.

Use `/imark-review <file.md>` to open one Markdown file in Imark and wait for **Approve** or **Send Back**. It is for plans, specs, RFCs, and docs—not source-code review.

Treat each active note as a request. Refer to it by its quoted text. When acted on, retain its block and add `resolved="YYYY-MM-DD"` to the opening `<!-- imark` line. Orphan notes lost their anchor; ask rather than infer context.

Do not hand-parse or hand-write Imark comment blocks. The managed Imark bridge preserves upstream parsing and review protocol.
