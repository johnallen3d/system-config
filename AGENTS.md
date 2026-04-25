# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, Home Manager.

## Quick Reference

- **Apply macOS**: `mise run nix-rebuild` (flake update + switch) or `mise run nix-rebuild -- --switch-only` (skip flake update)
- **Apply NixOS**: `sudo nixos-rebuild switch --impure --flake .#drummer`
- **Lint**: `nix flake check`
- **Search packages**: `nix search nixpkgs <name>`

### Rebuild Task (mandatory)

When rebuilding the macOS system, use **only** `mise run nix-rebuild`. Do not invoke `darwin-rebuild` or `nix flake update` directly.

The task writes full output to a temp log and prints `nix-rebuild log: <path>` to stderr on start and finish. It exits with the rebuild's exit code.

**Log access rules**:
- Do **not** read or stream the log on success — exit code 0 is the confirmation.
- Read the log **only when** (a) the task exits non-zero, or (b) the user explicitly asks to confirm/inspect output.
- Always query the log with **targeted `rg`** (e.g. `rg -i 'error|fail|warning' "$log"`, `rg -n 'building' "$log" | tail`). Never `cat`/`tail` the whole file — rebuild logs are large.

## Adding Packages

**Preference order**: nix packages > homebrew

**Package locations**:
- `modules/home-manager/packages/default.nix` - General packages (all platforms)
- `modules/home-manager/packages/darwin.nix` - macOS-only packages
- `modules/home-manager/packages/linux.nix` - Linux-only packages

**Process**:
1. Search nixpkgs first: `nix search nixpkgs <package-name>`
2. Add to appropriate file in `home.packages` list (alphabetically sorted)
3. Apply: `mise run nix-rebuild` (see Rebuild Task above)

## Policy

Never create git commits unless explicitly requested.

After changes to scripts, configs, packages — run `mise run nix-rebuild` so user can test immediately. Use `mise run nix-rebuild -- --switch-only` if no inputs need updating.

## Landing the Plane (Session Completion)

End session: complete ALL steps. Work NOT done until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished, update in-progress
4. **PUSH TO REMOTE** - MANDATORY:

   ```bash
   git pull --rebase
   bd sync
   ```

5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Context for next session

**CRITICAL RULES:**

- ALWAYS say "ready to push when you are" - YOU must NOT push

<!-- BEGIN BEADS INTEGRATION v:1 profile:full hash:d4f96305 -->
## Issue Tracking with bd (beads)

**IMPORTANT**: Project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers + relationships
- Git-friendly: Dolt-powered version control, native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking + confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim atomically**: `bd update <id> --claim`
3. **Work**: Implement, test, document
4. **New work found?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd auto-syncs via Dolt:

- Each write auto-commits to Dolt history
- Use `bd dolt push`/`bd dolt pull` for remote sync
- No manual export/import needed

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

See README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

End session: complete ALL steps. Work NOT done until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished, update in-progress
4. **PUSH TO REMOTE** - MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Context for next session

**CRITICAL RULES:**
- Work NOT complete until `git push` succeeds
- NEVER stop before pushing — leaves work stranded locally
- NEVER say "ready to push when you are" — YOU must push
- Push fails: resolve + retry until success

<!-- END BEADS INTEGRATION -->