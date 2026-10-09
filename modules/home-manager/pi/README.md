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

## Managed settings

Pi `settings.json` files remain writable, but rebuilds regenerate all configuration
from `modules/home-manager/pi-settings.nix`. Only `lastChangelogVersion` is
preserved as runtime bookkeeping. Interactive settings and package changes last
until the next rebuild; declare persistent changes in Nix. Removing a declaration
also removes its JSON key. Authentication and sessions are not managed.

Claude Code profiles are independent; the retired Claude Bridge integration and
its AskClaude prompt are no longer installed.

## Why this matters

The Mac personal `usage-footer` shows subscription quota percentages and reset
times for native `openai-codex` and proxied `subscription-codex`. The proxy route
queries its selected account through the managed `subscription-proxy codex-usage`
helper without downloading upstream OAuth tokens or falling back to another
local account. Actual returned quota windows are shown (some plans have only 7d).
Native Codex retains its existing active-profile `auth.json` lookup, with fallback
across `~/.config/pi-work` and `~/.config/pi`. This cross-profile legacy behavior
keeps the footer Mac-only; it remains excluded on Omarchy. Cloudflare MCP is
work-only, not part of personal Pi.

## Related files in this repo

- `modules/home-manager/pi-settings.nix` — authoritative writable Pi settings
- `modules/home-manager/pi-extensions.nix` — managed Pi extensions, skills, themes, legacy harness bridges
- `modules/home-manager/pi/packages.nix` — work profile installs `amfaro/agent-kit` from Git
- `modules/home-manager/claude-prompts.nix` — work Claude profile installs the `agent-kit@amfaro` plugin; old checkout-backed skill/command links are removed
- `modules/home-manager/pi/local-extensions.nix` — local Pi extensions
- `modules/home-manager/pi/extensions/usage-footer/index.ts` — footer showing provider/subscription usage

## Telegram bridge

`notes` runs the personal Pi profile, including its defaults and custom extensions, plus an explicit `pi-telegram` extension from `~/.config/pi-notes`; normal personal Pi stays bridge-free. The notes profile only maintains that package for `pi-refresh`. Its saved pairing remains in the package's existing `~/.pi/agent/telegram.json` location. The Pi wrapper patches the package's existing `session_start` handler to call its own polling startup, so it reconnects on startup, `/new`, `/resume`, and `/reload` without another polling loop. `/telegram-disconnect` stops it for current session; next session reconnects. The patch is reapplied after each package install; remove the notes package spec and patch block, then rebuild, to roll back.

## Legacy harness integrations

Some harness installers still hardcode `~/.pi/agent/extensions`.

This repo bridges declared legacy entries from that location into both managed Pi profiles with Home Manager symlinks, so one install can show up in:

- `~/.config/pi`
- `~/.config/pi-work`

Current bridge set:

- extension: `supacode`

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
