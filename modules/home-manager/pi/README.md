# Pi profile mapping

This repo manages two Pi profiles and their matching Claude Code profiles.

## Profile pairs

- `~/.config/pi` ↔ `~/.config/claude-personal`
- `~/.config/pi-work` ↔ `~/.config/claude-gmatter`

## Intended usage

### Personal

- Pi config dir: `~/.config/pi`
- Claude config dir: `~/.config/claude-personal`
- Use for personal/local work

### Work

- Pi config dir: `~/.config/pi-work`
- Claude config dir: `~/.config/claude-gmatter`
- Use for work context

## Why this matters

When Pi uses `claude-bridge`, Claude usage/account details come from the Claude Code profile behind that Pi profile. If the Pi profile and Claude profile do not match, footer usage/account info can look wrong.

The `usage-footer` extension now auto-maps by `PI_CODING_AGENT_DIR`:

- `~/.config/pi` → `~/.config/claude-personal`
- `~/.config/pi-work` → `~/.config/claude-gmatter`

Override remains available with `PI_USAGE_FOOTER_CLAUDE_CONFIG_DIR` if needed.

## Related files in this repo

- `modules/home-manager/pi-settings.nix` — Pi settings + Claude bridge settings
- `modules/home-manager/pi/local-extensions.nix` — local Pi extensions
- `modules/home-manager/pi/extensions/usage-footer/index.ts` — footer showing provider/subscription usage

## Model usage summaries

The nix-managed `pi-model-usage` command summarizes model/provider usage for Pi parent sessions and subagents.

Examples:

- `pi-model-usage` — latest session for selected profile
- `pi-model-usage current` — alias for latest
- `pi-model-usage recent`
- `pi-model-usage recent 10`
- `pi-model-usage recent:10`
- `pi-model-usage --aggregate recent`
- `pi-model-usage --aggregate recent 10`
- `pi-model-usage --json --aggregate recent 10`
- `pi-model-usage --csv recent 10`
- `pi-model-usage --profile work`
- `pi-model-usage --repo ~/dev/src/other-repo`
- `pi-model-usage --repo . recent 20`
- `pi-model-usage --all-repos recent 20`
- `pi-model-usage <session-id>`
- `pi-model-usage <session-path>`

Profile selection:

- `--profile auto` (default) uses `PI_CODING_AGENT_DIR` when set, otherwise searches both `~/.config/pi` and `~/.config/pi-work`
- `latest`, `current`, and `recent` are profile-scoped by default
- `--repo PATH` narrows those selectors to one repo
- `--all-repos` is an explicit no-filter alias for profile scope
- `--profile personal` forces `~/.config/pi`
- `--profile work` forces `~/.config/pi-work`
- `mise run pi-model-usage -- ...` and `mise run pi-m -- ...` are repo-local wrappers around the global command

## Model usage dashboard

The nix-managed `pi-model-usage-dashboard` command builds a local HTML dashboard from `pi-model-usage --json` output.

Why this shape:

- reuses the existing nix-managed session parser and JSON schema instead of duplicating raw JSONL parsing again
- stays local-first and lightweight (single HTML file, no web service or external SaaS)
- remains easy to launch from either shell or `mise`

Examples:

- `pi-model-usage-dashboard`
- `pi-model-usage-dashboard --limit 100`
- `pi-model-usage-dashboard --profile work`
- `pi-model-usage-dashboard --repo ~/dev/src/system-config`
- `pi-model-usage-dashboard --no-open --output ~/tmp/pi-usage.html`
- `mise run pi-model-usage-dashboard -- --limit 100 --repo .`

Current views:

- filter by profile, repo, provider, model, and session-path text
- aggregate cards for responses, tokens, cache read/write, and cost
- day/provider/model/repo breakdowns
- session list with drill-down into per-log model buckets

## Rule of thumb

If you change Pi profile wiring, also verify the corresponding Claude profile wiring.
