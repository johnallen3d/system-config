# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Task scope

- John's requested outcome is the scope boundary. Ask before adding optional documentation, tests, or source changes. A direct operation on a user-owned external file needs no repository edits or worktree.
- Verify the requested outcome directly; optional or unrelated checks never become blockers. Safety, authorization, issue-tracking, and both-host verification requirements still apply.

## Minimal checks only — strict policy

- This is a personal config, not a product. Keep repository checks to the minimum protecting concrete, critical behavior; delete redundant, speculative, or low-value checks.
- Never add or expand tests, fixtures, harnesses, or test dependencies without John's explicit approval for that specific addition; first explain the failure it prevents and why a smaller direct check is insufficient. A feature request or existing suite is not approval.
- Never test the wording or presence of agent instructions, prompts, docs, or policy clauses; review those directly.
- Evaluation, builds, activation, and runtime must not depend on `tests/` or repository validation scripts, including by inlining them into production modules. Retained checks stay explicit and opt-in.
- Run only the smallest check that proves the outcome — never the whole test directory or unrelated suites. If a check's necessity is unclear, ask.

## Omarchy is already Nix-managed

- Omarchy (Arch Linux, not NixOS) already uses this repo's standalone Home Manager: `homeConfigurations."johna@omarchy"` in `hosts/omarchy.nix`, home `/home/johna`. Don't ask whether it uses Home Manager.
- Keep host modules opt-in, leave Omarchy's native desktop config alone, and never run macOS rebuild tasks there. Shared project declarations and user automation belong in Nix/Home Manager, not separate mise tasks; project dependencies use mise.
- `~/dev/src/amfaro/mise.toml` is Home Manager-owned profile context on both hosts (`modules/home-manager/agent-projects.nix`). Use plain `pi`/`claude` (no named launchers), `mise exec` for noninteractive work commands, and respect `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`.
- See `docs/omarchy-agents.md` (activation, profiles) and `docs/omarchy-herdr.md` (Herdr, remote access).

## Theme

- `rose-pine`; edit `activeVariant` in `modules/home-manager/managed-theme.nix`.
- Telegram theme: `~/.local/share/theme/telegram-managed.tdesktop-theme`, chosen once via Chat Settings → Chat Wallpaper → Choose from file. Never manage `tdata`.

## Commands

- `mise update-system` (macOS): updates inputs, then deploys Mac and Omarchy in parallel. Flags: `--switch-only` (no input update), `--picker-only`, `--local-only` (skip Omarchy), `--harness-refresh` (refresh Pi packages and the work Claude plugin after deploys succeed), `--harness-only`. Either host failing returns nonzero and reports a partial deployment.
- `mise run harness-refresh` refreshes both hosts from Mac (host-local on Linux); it doesn't update Claude's binary or activate Home Manager. Restart Claude Code after a plugin update.
- Mac-only rebuild without Pi: `mise run nix-rebuild`. NixOS: `sudo nixos-rebuild switch --impure --flake .#drummer`.
- Check: `nix flake check`; search: `nix search nixpkgs <name>`.

## Policy

- Never run `darwin-rebuild` or `nix flake update` directly; use the commands above.
- Rebuilds print `nix-rebuild log: <path>`. Inspect logs only on failure or request with targeted `rg -i 'error|fail|warning' "$log"`; never stream a whole log.
- Prefer Nix to Homebrew. Search first, then add alphabetically to `modules/home-manager/packages/default.nix` (all), `darwin.nix`, or `linux.nix`.
- Apply Nix-managed script/config/package changes immediately (`--switch-only` when inputs are unchanged). Rebuilding doesn't reload app config: after Herdr changes run `herdr server reload-config`; reload running Ghostty instances as `.mise/tasks/theme-switch` does (AppleScript on macOS, `SIGUSR2` on Linux; skip if not running).
- Never commit unless explicitly requested.

## Deployment

- Changes to config shared by Mac and Omarchy (agents, project context, user automation) must be applied and verified on **both** unless John requests one host. A Mac rebuild is not an Omarchy deployment.
- Deploy shared changes with `mise exec -- system-config-deploy "$task_path" --switch-only` (works for older task worktrees too) or `mise update-system --switch-only` from the Mac task worktree. Use `mise run nix-rebuild --switch-only` only for explicitly Mac-only changes; `docs/omarchy-agents.md` has the manual Linux-only/recovery procedure.
- Before activation, check each host: `mise exec -- python3 ~/.local/share/system-config-deploy/.mise/scripts/deployment_state.py status "$task_path"`. Only the kernel lock means busy; wait or retry, never bypass it. Manual Home Manager activation must use the same coordinator.
- The coordinator composes temporary source from integrated local `main` plus verified already-active task layers (no commits, branches, or worktrees). Composition is file-level: differing edits to the same file (including `flake.lock`) stop with paths and owners. Investigate conflicts and provenance yourself; ask John only for real decisions or new authorization. Never add unactivated or merely dirty work.
- Missing or drifted provenance blocks activation. Adoption needs verified ownership and an exact evaluated-output match to the installed generation — never guess from timestamps or build success. Reconcile out-of-band rollbacks explicitly. Details: `docs/concurrent-deployments.md`.
- Authorized deployment includes clean fast-forward sync of Omarchy's `main` to reviewed, integrated local `main`, without separate merge permission. Stop on dirty source, divergence, conflicts, or uncertain ownership; preserve unrelated remote edits and credentials. Carrying layers or syncing never authorizes commits, merges, rebases, pushes, worktree removal, agent restarts, or card closure.
- SSH is `johna@omarchy` with a Fish login shell: run Bash via `bash -s`, work-profile commands via `mise -C ~/dev/src/amfaro exec -- ...` with absolute script paths.
- Verify installed config and effective runtime on each host independently. Don't restart active agents or Herdr servers just to refresh environment; report needed restarts. If a host is unreachable or verification fails, the deployment is **partial**: keep the card open, name the pending host/action, and never report it as done. Documentation-only changes need no activation.
- Pi Pocket (`pi-pocket.service`, `docs/pi-pocket.md`) is the production personal assistant.

## Issue tracking

Use Fizzy only (board from `.fizzy.yaml`; use the CLI's `--jq`). Card commands take the card `number`.

1. Search with `fizzy card list --all --jq '[.data[] | {number, title}]'`. If no card covers the task, create one before repository changes; every task needs a card.
2. Claim it with `fizzy card self-assign <number>` when appropriate. File discoveries with `fizzy card create --board <board-id> --title "..." --description "..."` and link them from the originating card.
3. Add progress and completion comments.

**Closing a card requires John's explicit request or an actual `/wrap` invocation** (its expanded prompt counts; mentioning, quoting, or reading the prompt file doesn't). Task completion, deployment, commits, "done", or "wrap up" never authorize closure. On `/wrap`, close completed in-scope cards after checking completion and deployment — never blocked or partially deployed work.

## Session completion

1. Update cards and file remaining work; apply the closure rule above.
2. Run only the smallest task-relevant checks.
3. Run `git status` and report staged/unstaged changes.
4. Hand off changes, validation, and next steps, with Mac and Omarchy deployment status reported separately.

Wrap-up never authorizes a rebuild or `git push`. Say `ready to push when you are` only if a local commit exists and push is the only remaining step; otherwise `ready to commit when you are`.
