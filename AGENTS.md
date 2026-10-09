# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Omarchy is already Nix-managed

- John's Omarchy machine **already uses this repository's standalone Home Manager setup** on Arch Linux. Do not assume Omarchy is outside Nix or ask whether it uses Home Manager.
- Its flake output is `homeConfigurations."johna@omarchy"`, configured in `hosts/omarchy.nix`; its home directory is `/home/johna`.
- `~/dev/src/amfaro/mise.toml` is shared Home Manager-owned profile context on Mac and Omarchy (`modules/home-manager/agent-projects.nix`). Use plain `pi`/`claude`; use `mise exec` explicitly for noninteractive work commands. Respect both profile variables, including `PI_CODING_AGENT_DIR`; no named profile launchers are installed.
- Shared project declarations and user-level automation belong in this Nix/Home Manager setup by default, not a separate mise task merely because the target is Omarchy. Project dependencies are managed with mise.
- Omarchy is not NixOS. Keep host modules opt-in and leave Omarchy's native desktop configuration alone; never run macOS rebuild tasks there.
- Consult `docs/omarchy-agents.md` for activation and agent profiles, and `docs/omarchy-herdr.md` for Herdr and remote access. Respect `PI_CODING_AGENT_DIR` when working with Pi profiles.

## Theme

- Theme: `rose-pine`; edit `activeVariant` in `modules/home-manager/managed-theme.nix`.
- Telegram theme output: `~/.local/share/theme/telegram-managed.tdesktop-theme`. Choose it once in Chat Settings → Chat Wallpaper → Choose from file; it reloads on launch. Never manage `tdata` declaratively.

## Commands

- macOS: `mise update-system`; `--switch-only` skips flake updates, `--harness-refresh` refreshes Pi packages and the work Claude plugin on **Mac and Omarchy** after the Mac rebuild, and `--harness-only` refreshes both hosts without rebuilding (`mise run harness-refresh` also works). `mise run harness-refresh --local-only` explicitly skips Omarchy; on Linux the task is always host-local. Failures on either host return nonzero. These tasks do not update Claude's binary or activate Omarchy. Restart Claude Code on each refreshed host after a plugin update.
- macOS rebuild without Pi: `mise run nix-rebuild`.
- NixOS: `sudo nixos-rebuild switch --impure --flake .#drummer`.
- Check: `nix flake check`; search: `nix search nixpkgs <name>`.

## Policy

- Apply macOS only with the repo-local commands above; never run `darwin-rebuild` or `nix flake update` directly.
- Rebuild tasks print `nix-rebuild log: <path>` and return the rebuild status. Inspect logs only on failure/request with targeted `rg` (for example `rg -i 'error|fail|warning' "$log"`); never stream a whole log.
- Prefer Nix to Homebrew. Search first, then add alphabetically to `modules/home-manager/packages/default.nix` (all), `darwin.nix` (macOS), or `linux.nix` (Linux).
- Apply executable script/config/package changes immediately; use `--switch-only` when inputs are unchanged. A rebuild alone does not reload application config.
- After applying Herdr config changes, run `herdr server reload-config`.
- After applying Ghostty config changes, reload each running instance with its `reload_config` action (AppleScript on macOS, `SIGUSR2` on Linux); use the guarded platform behavior in `.mise/tasks/theme-switch` and skip when Ghostty is not running.
- Never commit unless explicitly requested.

## Shared Mac/Omarchy deployment

- Before changing shared agent, project-context, or user-automation config, identify which hosts import it. Unless John explicitly requests a single-host change, changes shared by Mac and Omarchy must be applied and verified on **both**; a Mac rebuild is not an Omarchy deployment.
- Use the repo-local macOS apply command and Omarchy's standalone Home Manager activation from `docs/omarchy-agents.md`, without updating inputs when unchanged. Do not run macOS tasks on Omarchy.
- Omarchy currently activates from `~/dev/src/system-config-amfaro`, a working-tree snapshot, not an automatically synchronized checkout. A local edit, commit, or push does not update that snapshot or its installed config. Inspect the actual remote source and installed state before applying; transfer only intended changes after checking for divergence. Preserve unrelated remote edits and credentials; stop and report conflicts rather than overwriting them.
- SSH connects as `johna@omarchy`; its login shell is Fish. Run Bash scripts explicitly with `bash -s`, and use `mise -C ~/dev/src/amfaro exec -- ...` for noninteractive work-profile commands. Use absolute script paths when `mise -C` changes the working directory.
- Verify installed config and effective profile/runtime behavior independently on each host, not just source files or build success. Do not restart active agents or Herdr servers merely to refresh environment; report any required agent restart explicitly.
- If a host is unreachable, synchronization is blocked, or verification fails, the shared deployment is **partial**. Keep its Fizzy card open and name the pending host/action in the handoff. Never report unqualified "applied", "done", or "ready to push" while deployment remains pending.
- Documentation-only changes do not require activation. Keep these deployment instructions available in Omarchy's active snapshot too.

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
4. Hand off changes, validation, and next steps. For shared config changes, report Mac and Omarchy deployment/verification status separately, including pending activation or agent restarts.

Wrap-up alone never authorizes a rebuild or `git push`. Say `ready to push when you are` only if a local commit exists and push is the sole remaining step; otherwise say `ready to commit when you are` or simply hand off.
