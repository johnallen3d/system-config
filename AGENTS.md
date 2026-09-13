# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

- Theme: `rose-pine`; edit `activeVariant` in `modules/home-manager/managed-theme.nix`.
- Telegram theme output: `~/.local/share/theme/telegram-managed.tdesktop-theme`. Choose it once in Chat Settings → Chat Wallpaper → Choose from file; it reloads on launch. Never manage `tdata` declaratively.

## Commands

- macOS: `mise update-system`; `--switch-only` skips flake updates, `--pi-refresh` refreshes Pi, and `--pi-only` updates only Pi.
- macOS rebuild without Pi: `mise run nix-rebuild`.
- NixOS: `sudo nixos-rebuild switch --impure --flake .#drummer`.
- Check: `nix flake check`; search: `nix search nixpkgs <name>`.

## Policy

- Apply macOS only with the repo-local commands above; never run `darwin-rebuild` or `nix flake update` directly.
- Rebuild tasks print `nix-rebuild log: <path>` and return the rebuild status. Inspect logs only on failure/request with targeted `rg` (for example `rg -i 'error|fail|warning' "$log"`); never stream a whole log.
- Prefer Nix to Homebrew. Search first, then add alphabetically to `modules/home-manager/packages/default.nix` (all), `darwin.nix` (macOS), or `linux.nix` (Linux).
- Apply executable script/config/package changes immediately; use `--switch-only` when inputs are unchanged.
- Never commit unless explicitly requested.

## Issue tracking

Use Fizzy only—no Markdown TODOs, other trackers, or duplicate cards. The project board is selected by `.fizzy.yaml`. Use the CLI's built-in `--jq` for programmatic output.

1. Check existing work with `fizzy card list --all --jq '[.data[] | {number, title}]'` and search before creating a card.
2. Claim an existing card with `fizzy card self-assign <number>` when appropriate.
3. File discoveries with `fizzy card create --board <board-id> --title "Title" --description "Context"` and relate them in the originating card's description or comments.
4. Finish with `fizzy card close <number>`.

Card commands use the card `number`, not its internal ID. Use board columns for workflow state and tags for type or priority when useful.

## Session completion

1. File remaining work and update/close issues.
2. Run relevant quality gates.
3. Run `git status`; report staged/unstaged changes.
4. Hand off changes, validation, and next steps.

Wrap-up alone never authorizes a rebuild or `git push`. Say `ready to push when you are` only if a local commit exists and push is the sole remaining step; otherwise say `ready to commit when you are` or simply hand off.
