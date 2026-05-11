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

## Rule of thumb

If you change Pi profile wiring, also verify the corresponding Claude profile wiring.
