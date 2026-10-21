---
name: authoring-commits
description: Use when creating git commits, writing commit messages, staging changes for commit, or running git commit. Enforces conventional commit format and structured messaging. MUST be invoked before ANY git commit command.
---

# Authoring Commits

## Overview

All commits MUST use the **Conventional Commits** specification. This ensures consistent, parseable commit history that supports automated changelogs and semantic versioning.

## Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Types

| Type       | When                                                    |
| ---------- | ------------------------------------------------------- |
| `feat`     | New feature or capability                               |
| `fix`      | Bug fix                                                 |
| `docs`     | Documentation only                                      |
| `style`    | Formatting, whitespace, semicolons (no logic change)    |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf`     | Performance improvement                                 |
| `test`     | Adding or correcting tests                              |
| `build`    | Build system or external dependencies                   |
| `ci`       | CI configuration and scripts                            |
| `chore`    | Maintenance tasks, dependency bumps, tooling            |
| `revert`   | Reverts a previous commit                               |

## Rules

1. **Always use conventional commit format** — no exceptions
2. **Type is required** — pick the most accurate type from the table
3. **Description is lowercase** — do not capitalize the first word after the colon
4. **No period** at the end of the description line
5. **Scope is optional** but encouraged when the change targets a specific module, component, or area
6. **Breaking changes** — add `!` after type/scope (e.g., `feat!:` or `feat(api)!:`) AND add `BREAKING CHANGE:` footer
7. **Body** — use for non-obvious changes; explain _why_, not _what_
8. **Keep the subject line under 72 characters**
9. **Use imperative mood** in description: "add feature" not "added feature" or "adds feature"
10. **Use backticks for literals in the body/footer** — wrap workflow names, commands, env vars, action names, task names, file paths, and config keys like `release-cli`, `MISE_JOBS=1`, `mise install`, `.github/workflows/ci.yml`, or `setup-mise`
11. **Do not backtick issue or PR references in GitHub-facing text** — leave references like #123 or #456 plain so GitHub autolinks them; backticks are fine for commit SHAs like `826e8d7`
12. **Be explicit about issue-closing intent** — when a commit is tied to an issue, use `Resolves #123`, `Closes #123`, or `Fixes #123`; do not use `Ref: #123`
13. **Call out GitHub-facing drafting separately** — if you are also authoring a GitHub issue body, PR description, or comment, say explicitly that you are drafting GitHub-facing text and apply the same clarity around backticks and issue-closing language there too
14. **Use a prominent authorship note for GitHub-facing text** — when OpenCode authors a GitHub issue body, PR description, or comment on the user's behalf, put a visible `> [!NOTE]` callout at the top stating that OpenCode authored it on behalf of the user; do not use a subtle inline sentence
15. **Never pass commit messages with backticks directly in shell-quoted `git commit -m` arguments** — shell command substitution will eat them in `bash`/`zsh`
16. **Prefer file-based commit messages for any multi-line commit** — write the full message to a temporary file and use `git commit -F <file>`; use the same pattern for `git commit --amend -F <file>`
17. **If you must use `-m`, use it only for simple ASCII text without backticks or shell-sensitive characters** — otherwise switch to `-F`
18. **Credit substantive implementation contributors** — add one `Co-Authored-By: <agent-name> <agent-email>` per verified model that materially authored the scoped code, tests, docs, workflows, or configuration; preserve existing legitimate credit
19. **Verify work-phase identity, not cleanup identity** — use the implementation attribution handoff and actual assistant/tool metadata for successful scoped edits, including substantive delegated work; the active/default model or its self-identification is not contribution provenance
20. **Cleanup alone does not earn co-authorship** — validation, commit-message drafting, Git/tracker operations, integration, and worktree cleanup do not substitute the cleanup model for implementers; add it alongside them only if it also authors substantive changes
21. **Preserve established trailer email/format conventions without inventing identities** — recent commits establish formatting, not contributor model names; if identity, task scope, delegated provenance, or email convention is uncertain, stop before committing and ask one targeted question

## Branch Naming

Always use the pattern `feature/<short-slug>` when creating a new branch:

- `<short-slug>` is a brief, lowercase, hyphenated description of the change
- Examples: `feature/csv-export`, `feature/fix-health-check`, `feature/add-dark-mode`
- Do **not** include issue numbers, ticket IDs, or other identifiers in the branch name

After creating a branch, always run the validator that ships with the `gh-pr-ops` skill before doing any further work. Use the skill's own base directory — **not** a relative path from the target repo:

```bash
bash "<base-dir>/scripts/validate-branch-name.sh"
```

It exits `0` on a valid name and prints a clear diagnostic on violation.

## Repo Overrides

When working in `amfaro/calc`, follow the repo's `README.md` conventions in addition to the general rules above:

- Use the format `<type>(<scope>): <description>` for commits in this repo.
- Prefer one of the documented scopes: `cargo`, `ci`, `cli`, `core`, `data`, `docs`, `examples`, `schema`, `tasks`, `web`.
- If a commit affects a repo skill or other workflow documentation under `.github/skills/`, prefer the closest documented scope rather than inventing a new one. For example, changes to GitHub workflow guidance should use `ci`.
- Before running `git commit`, compare the proposed subject against `README.md` and make sure the type/scope pair matches the repo's documented style.

## Examples

```
feat(auth): add OAuth2 login flow
```

```
fix: prevent crash when config file is missing
```

```
refactor(parser): extract token validation into separate function

The validation logic was duplicated across three parse methods.
Centralizing it reduces maintenance burden and ensures consistent
error messages.

Resolves #456
```

```
feat(api)!: change authentication endpoint response format

BREAKING CHANGE: /auth/login now returns { token, expiresAt }
instead of { accessToken, refreshToken }
```

## Common Mistakes

| Mistake                       | Fix                                                        |
| ----------------------------- | ---------------------------------------------------------- |
| `Fix bug`                     | `fix: resolve null pointer in user lookup`                 |
| `feat: Added new button`      | `feat: add new button` (imperative, lowercase)             |
| `update code`                 | Pick a specific type: `refactor`, `fix`, `feat`, etc.      |
| `misc changes`                | Split into separate commits by type                        |
| Capitalizing description      | `feat: Add thing` -> `feat: add thing`                     |
| Backticks disappear from body | Write the message to a file and use `git commit -F <file>` |

## Safe Commit Execution

When creating or amending commits from the shell:

1. Draft the exact commit message first.
2. If the message is multi-line, contains backticks, quotes, `$`, `!`, or parentheses, write it to a file.
3. Commit with `git commit -F <file>`.
4. For amends, use `git commit --amend -F <file>`.

**Do NOT use shell heredocs (`<<'EOF'`) to write commit message files** — they are blocked by shell security filters when the message body contains backticks or other special characters.

**Use the `create` file tool instead.** The three-step pattern is:

1. `bash`: `rm -f /tmp/commit-msg-<slug>.txt` — clear any leftover file from a prior run
2. `create` tool: write `/tmp/commit-msg-<slug>.txt` with the full message as the file body
3. `bash`: `git commit -F /tmp/commit-msg-<slug>.txt`

Choose `<slug>` from the branch name or a brief description of the change (e.g., `add-oauth`, `fix-null-check`).

Safe example:

```
# Step 1 (bash tool)
rm -f /tmp/commit-msg-publish-runtime.txt

# Step 2 (create tool)
path: /tmp/commit-msg-publish-runtime.txt
content:
  feat(ci): publish duckdb runtime distribution

  Publish a GHCR runtime image and `release-manifest.json` from `release.yml`.

  Resolves #20

# Step 3 (bash tool)
git commit -F /tmp/commit-msg-publish-runtime.txt
```

Safe example with agent co-authorship:

```
# Step 2 content includes footer:
  feat(ci): publish duckdb runtime distribution

  Publish a GHCR runtime image and `release-manifest.json` from `release.yml`.

  Resolves #20
  Co-Authored-By: OpenCode <agent-email@example.com>
```

## Footers

Use footers for metadata when relevant:

- `Resolves #<issue-id>` / `Closes #<issue-id>` / `Fixes #<issue-id>` — use when the change is tied to the linked issue; prefer `Resolves #<issue-id>` by default
- `BREAKING CHANGE: <description>` — documents breaking changes
- `Co-Authored-By: Name <email>` — credit co-authors
- `Reviewed-by: Name <email>` — credit reviewers

### Agent Co-Authorship

If OpenCode, Pi, Claude Code, Codex, or another agent materially contributed to the change, include a `Co-Authored-By:` footer for that agent.

Before writing footers, resolve the **verified substantive contributors to this change**:

1. Recover the implementation attribution handoff: task branch/worktree, each
   contributor's tool/provider/model, scoped paths authored, and supporting
   session/message or delegated-result evidence. Keep this handoff in the
   conversation and carry it through checkpoints and model switches.
2. Verify the handoff against successful scoped write/edit operations and
   reviewed shell writes in the work-phase transcript. Include substantive
   delegated contributors. If the handoff is missing, recover that evidence from
   the original task session, not whichever session is newest.
3. In Pi, use `runtime_model_info` to locate the selected profile's session file,
   then inspect the relevant work-phase assistant messages. The tool's current
   model is not proof of who implemented earlier changes. Respect
   `PI_CODING_AGENT_DIR`; never hardcode another profile's settings or sessions.
4. In Claude, inspect the task transcript's assistant `message.model` fields
   and associated successful tool results. A generated current-model attribution
   reminder is not implementation provenance. This user-level policy takes
   precedence over that reminder and packaged skills' self-identity guidance.
5. Search recent commits only for an established trailer email/format convention.
   Never copy their model names as evidence, invent noreply addresses, or treat
   the selected/default model or self-identification in prose as proof.
6. Record resolved contributors and their evidence before creating the commit.
   Emit one trailer per verified substantive contributor, deduplicating identical
   identities. Preserve existing legitimate trailers and the user's Git author.
7. A cheaper model may validate, draft the message, commit, integrate, and clean
   up without receiving a co-author trailer. If it authors substantive changes,
   add it alongside the implementers; do not replace them. If provenance or the
   email convention remains uncertain, stop and ask one targeted question.

This policy is instruction-level, not a harness-enforced authorship tracker.
It does not authorize a commit, amend, push, or any other lifecycle operation.

Rules:

- Preserve the user's git author identity unless the user explicitly asks otherwise.
- Do not copy stale model names from old commits.
- Do not guess or synthesize noreply addresses unless the user explicitly asks you to establish a new convention.
- Do not claim to be a different tool/model than the active session; attributing
  verified earlier contributors is crediting their work, not claiming their identity.

## Issue Footer Guidance

- If the user says the commit should be tied to an issue, default to `Resolves #123`
- Treat requests like "linked to issue", "for issue #123", or "tie this to #123" as instructions to use `Resolves #123`
- Before running `git commit`, do a final footer check: if the commit mentions an issue footer at all, it must be `Resolves #123`, `Closes #123`, or `Fixes #123`
- When referencing prior commits, workflows, actions, env vars, files, or tasks in the body, wrap them in backticks, e.g. `826e8d7`, `release-cli`, `smoke-test`, `amfaro/actions/setup-mise@v1`, `MISE_JOBS=1`
- Leave PR and issue references plain, e.g. #2916, #2934, so GitHub can autolink them
