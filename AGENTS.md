# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Task scope

- These repository workflows govern repository and Nix-managed changes. They do not require turning a direct operation on a user-owned external file into repository edits or a worktree.
- Keep John's requested outcome as the scope boundary. Do not add documentation, tests, or source changes merely to make a broader workflow consistent; ask before adding optional work.
- Verify the requested outcome directly. Unrelated or optional checks must not become blockers for an otherwise independent operation.
- All applicable safety, authorization, issue-tracking, and both-host verification requirements still apply to the actual task.

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

- macOS: `mise update-system` updates inputs once, then applies **Mac and Omarchy in parallel**. `--switch-only` skips input updates; `--picker-only` updates only the shared picker; `--local-only` explicitly skips Omarchy. The task synchronizes integrated local `main` to clean, fast-forwardable Omarchy `main`, then deploys the invoking source (including nonignored uncommitted files) in a dedicated linked worktree; it never overwrites unrelated remote changes or removes worktrees. Either host failing returns nonzero and reports a partial deployment.
- `--harness-refresh` refreshes Pi packages and the work Claude plugin after both requested deployments succeed; `--harness-only` skips configuration deployment. `mise run harness-refresh` also refreshes both hosts from Mac; `--local-only` explicitly skips Omarchy. On Linux harness refresh is host-local. Harness refresh does not update Claude's binary or activate Home Manager. Restart Claude Code on each refreshed host after a plugin update.
- macOS rebuild without Pi: `mise run nix-rebuild`.
- NixOS: `sudo nixos-rebuild switch --impure --flake .#drummer`.
- Check: `nix flake check`; search: `nix search nixpkgs <name>`.

## Policy

- Apply macOS only with the repo-local commands above; never run `darwin-rebuild` or `nix flake update` directly.
- Rebuild tasks print `nix-rebuild log: <path>` and return the rebuild status. Inspect logs only on failure/request with targeted `rg` (for example `rg -i 'error|fail|warning' "$log"`); never stream a whole log.
- Prefer Nix to Homebrew. Search first, then add alphabetically to `modules/home-manager/packages/default.nix` (all), `darwin.nix` (macOS), or `linux.nix` (Linux).
- Apply Nix-managed executable script/config/package changes immediately; use `--switch-only` when inputs are unchanged. Direct changes to user-owned external files do not require a Nix rebuild. A rebuild alone does not reload application config.
- After applying Herdr config changes, run `herdr server reload-config`.
- After applying Ghostty config changes, reload each running instance with its `reload_config` action (AppleScript on macOS, `SIGUSR2` on Linux); use the guarded platform behavior in `.mise/tasks/theme-switch` and skip when Ghostty is not running.
- Never commit unless explicitly requested.

## Shared Mac/Omarchy deployment

- Before changing shared agent, project-context, or user-automation config, identify which hosts import it. Unless John explicitly requests a single-host change, changes shared by Mac and Omarchy must be applied and verified on **both**; a Mac rebuild is not an Omarchy deployment.
- For shared Nix-managed configuration changes, run `mise update-system --switch-only` from the verified Mac task worktree; it also builds/activates Omarchy's standalone Home Manager configuration. Use `mise run nix-rebuild --switch-only` only for an explicitly Mac-only deployment. The manual Omarchy procedure in `docs/omarchy-agents.md` remains available for Linux-only changes/recovery. Do not run macOS tasks on Omarchy.
- Omarchy deployment source belongs to its `~/dev/src/system-config` Git repository and task-linked worktrees, not standalone snapshots. The former `system-config-poc` and `system-config-amfaro` paths were retired; recovery archives are not deployment sources. Keep Omarchy's local `main` synchronized with reviewed, integrated Git history, then create deployment worktrees from that `main`. Do not copy newer source over an old checkout without advancing its recorded history. Inspect source, lock, worktree ownership, and installed state; transfer only intended changes after checking divergence. Preserve unrelated remote edits and credentials; stop and report conflicts rather than overwriting them. Hermes uses its upstream gateway under ordinary systemd management; no bespoke approval, receipt, or migration controller gates apply.
- SSH connects as `johna@omarchy`; its login shell is Fish. Run Bash scripts explicitly with `bash -s`, and use `mise -C ~/dev/src/amfaro exec -- ...` for noninteractive work-profile commands. Use absolute script paths when `mise -C` changes the working directory.
- Verify installed config and effective profile/runtime behavior independently on each host, not just source files or build success. Do not restart active agents or Herdr servers merely to refresh environment; report any required agent restart explicitly.
- If a host is unreachable, synchronization is blocked, or verification fails, the shared deployment is **partial**. Keep its Fizzy card open and name the pending host/action in the handoff. Never report unqualified "applied", "done", or "ready to push" while deployment remains pending.
- Documentation-only changes do not require activation. Keep these deployment instructions available in Omarchy's Git-based deployment source too.

## Issue tracking

Use Fizzy only—no Markdown TODOs, other trackers, or duplicate cards. The project board is selected by `.fizzy.yaml`. Use the CLI's built-in `--jq` for programmatic output.

1. Check existing work with `fizzy card list --all --jq '[.data[] | {number, title}]'` and search before creating a card.
2. Claim an existing card with `fizzy card self-assign <number>` when appropriate.
3. File discoveries with `fizzy card create --board <board-id> --title "Title" --description "Context"` and relate them in the originating card's description or comments.
4. Add progress/completion comments; leave cards open unless John explicitly requests closure directly or actually invokes `/wrap`. Only then may you run `fizzy card close <number>` within that authorization's scope.

**Card closure requires John's explicit authorization.** Task completion, successful deployment, committing, ordinary session-ending language (including "wrap up" or "done"), and merely mentioning/quoting `/wrap` do not authorize closure. An actual `/wrap` invocation authorizes closing only completed cards within its scope, never blocked or partially deployed work. Without that authorization, report completion and keep the card open; no workflow, example, breadcrumb, or move to the `done` column overrides this rule.

Card commands use the card `number`, not its internal ID. Use board columns for workflow state and tags for type or priority when useful.

An actual `/wrap` invocation includes the command's expanded user prompt. On that invocation, you MUST close completed, in-scope cards after checking completion and deployment; do not misclassify the expanded invocation as a mere mention or quotation. Reading a prompt file through tools is not an invocation.

## Session completion

1. File remaining work and update issue comments. Keep cards open unless John explicitly requests closure directly or actually invokes `/wrap`; apply the closure authorization and scope rules above.
2. Run relevant quality gates.
3. Run `git status`; report staged/unstaged changes.
4. Hand off changes, validation, and next steps. For shared config changes, report Mac and Omarchy deployment/verification status separately, including pending activation or agent restarts.

Wrap-up alone never authorizes a rebuild or `git push`. Say `ready to push when you are` only if a local commit exists and push is the sole remaining step; otherwise say `ready to commit when you are` or simply hand off.
