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

Use `bd` only—no Markdown TODOs, external trackers, or duplicates. Use `--json` programmatically.

1. Check `bd ready --json`, then claim with `bd update <id> --claim --json`.
2. Implement and validate.
3. File discoveries with `bd create "Title" --description="Context" -t bug|feature|task -p 0-4 --deps discovered-from:<id> --json`.
4. Finish with `bd close <id> --reason="Done" --json`.

Types: `bug|feature|task|epic|chore`; priorities: 0 critical, 1 high, 2 default, 3 low, 4 backlog. Writes auto-commit to Dolt; remote pull/push requires an explicit request.

## Session completion

1. File remaining work and update/close issues.
2. Run relevant quality gates.
3. Run `git status`; report staged/unstaged changes.
4. Hand off changes, validation, and next steps.

Wrap-up alone never authorizes a rebuild, `git push`, `bd sync`, or `bd dolt push`. Say `ready to push when you are` only if a local commit exists and push is the sole remaining step; otherwise say `ready to commit when you are` or simply hand off.
