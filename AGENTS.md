# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Task scope

- John's requested outcome is the scope boundary. Ask before adding optional documentation, tests, or source changes. A direct operation on a user-owned external file needs no repository edits or worktree.
- Verify the requested outcome directly; optional or unrelated checks never become blockers. Safety, authorization, issue-tracking, and every-host verification requirements still apply.

## Minimal checks only — strict policy

- This is a personal config, not a product. Keep repository checks to the minimum protecting concrete, critical behavior; delete redundant, speculative, or low-value checks.
- Never add or expand tests, fixtures, harnesses, or test dependencies without John's explicit approval for that specific addition; first explain the failure it prevents and why a smaller direct check is insufficient. A feature request or existing suite is not approval.
- Never test the wording or presence of agent instructions, prompts, docs, or policy clauses; review those directly.
- Evaluation, builds, activation, and runtime must not depend on `tests/` or repository validation scripts, including by inlining them into production modules. Retained checks stay explicit and opt-in.
- Run only the smallest check that proves the outcome — never the whole test directory or unrelated suites. If a check's necessity is unclear, ask.

## Omarchy hosts are already Nix-managed

- Omarchy (Arch Linux, not NixOS) hosts already use this repo's standalone Home Manager: `homeConfigurations."johna@omarchy"` (`hosts/omarchy.nix`), `homeConfigurations."johna@miller"` (`hosts/miller.nix`), and `homeConfigurations."johna@drummer"` (`hosts/drummer.nix`) — Omarchy is a mini PC; Miller and Drummer are 2013 Mac Pros (hardware: `docs/hosts-hardware.md`) — sharing `hosts/omarchy-common.nix`. Only Omarchy runs the singletons (Pi Pocket, subscription proxy server, credits, Syncthing LAN forwarder); home `/home/johna`. Don't ask whether it uses Home Manager.
- Keep host modules opt-in, leave Omarchy's native desktop config alone, and never run macOS rebuild tasks there. Shared project declarations and user automation belong in Nix/Home Manager, not separate mise tasks; project dependencies use mise.
- `~/dev/src/amfaro/mise.toml` is Home Manager-owned profile context on every host (`modules/home-manager/agent-projects.nix`). Use plain `pi`/`claude` (no named launchers), `mise exec` for noninteractive work commands, and respect `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`.
- See `docs/omarchy-agents.md` (activation, profiles).

## Theme

- `rose-pine`; edit `activeVariant` in `modules/home-manager/managed-theme.nix`.
- Telegram theme: `~/.local/share/theme/telegram-managed.tdesktop-theme`, chosen once via Chat Settings → Chat Wallpaper → Choose from file. Never manage `tdata`.

## Commands

- `mise update-system` (macOS): updates inputs, then deploys Mac, Omarchy, Miller, and Drummer in parallel. Flags: `--switch-only` (no input update), `--local-only` (skip Linux hosts), `--harness-refresh` (refresh Pi packages and the work Claude plugin after deploys succeed), `--harness-only`. Any host failing returns nonzero and reports a partial deployment.
- `mise run harness-refresh` refreshes every host from Mac (host-local on Linux); it doesn't update Claude's binary or activate Home Manager. Restart Claude Code after a plugin update.
- Mac-only rebuild without Pi: `mise run nix-rebuild`.
- Switchyard (Rex floats) is the `switchyard` flake input (`~/dev/src/playground/switchyard`). Try local changes with `mise run switchyard-dev [checkout]` (Mac build, no activation). To ship: push switchyard, run `nix flake lock --update-input switchyard` here, then deploy to every host.
- Check: `nix flake check`; search: `nix search nixpkgs <name>`.

## Policy

- Never run `darwin-rebuild` or `nix flake update` directly; use the commands above.
- Rebuilds print `nix-rebuild log: <path>`. Inspect logs only on failure or request with targeted `rg -i 'error|fail|warning' "$log"`; never stream a whole log.
- Prefer Nix to Homebrew. Search first, then add alphabetically to `modules/home-manager/packages/default.nix` (all), `darwin.nix`, or `linux.nix`.
- Apply Nix-managed script/config/package changes immediately (`--switch-only` when inputs are unchanged). Rebuilding doesn't reload app config: reload running Ghostty instances as `.mise/tasks/theme-switch` does (AppleScript on macOS, `SIGUSR2` on Linux; skip if not running).
- Never commit unless explicitly requested.

## Deployment

- An actual `/wrap` in this repo deploys its committed shared-config changes: after integration into local `main` and before cleanup, it runs the deployment and verification below on every host. It closes the card only when every host succeeds; a failed or unreachable host keeps the card open, and the handoff names it. `/wrap` still never authorizes a push.
- Changes to config shared by Mac, Omarchy, Miller, and Drummer (agents, project context, user automation) must be applied and verified on **every** host unless John requests fewer. A Mac rebuild is not a Linux deployment.
- Deploy shared changes with `mise exec -- system-config-deploy "$task_path" --switch-only` (works for older task worktrees too) or `mise update-system --switch-only` from the Mac task worktree. Use `mise run nix-rebuild --switch-only` only for explicitly Mac-only changes; `docs/omarchy-agents.md` has the manual Linux-only/recovery procedure.
- Before activation, check each host: `mise exec -- python3 ~/.local/share/system-config-deploy/.mise/scripts/deployment_state.py status "$task_path"`. Only the kernel lock means busy; wait or retry, never bypass it. Manual Home Manager activation must use the same coordinator.
- The coordinator composes temporary source from integrated local `main` plus verified already-active task layers (no commits, branches, or worktrees). Composition is file-level: differing edits to the same file stop with paths and owners; a `flake.lock` holding every input another owner relocked, at that revision or newer, supersedes it. Investigate conflicts and provenance yourself; ask John only for real decisions or new authorization. Never add unactivated or merely dirty work.
- Missing or drifted provenance blocks activation. Adoption needs verified ownership and an exact evaluated-output match to the installed generation — never guess from timestamps or build success. Reconcile out-of-band rollbacks explicitly. Details: `docs/concurrent-deployments.md`.
- Authorized deployment includes clean fast-forward sync of each Linux host's `main` to reviewed, integrated local `main`, without separate merge permission. Stop on dirty source, divergence, conflicts, or uncertain ownership; preserve unrelated remote edits and credentials. Carrying layers or syncing never authorizes commits, merges, rebases, pushes, worktree removal, agent restarts, or card closure.
- SSH is `johna@omarchy` / `johna@miller` / `johna@drummer` with a Fish login shell: run Bash via `bash -s`, work-profile commands via `mise -C ~/dev/src/amfaro exec -- ...` with absolute script paths.
- Verify installed config and effective runtime on each host independently. Don't restart active agents just to refresh environment; report needed restarts. Verification means confirming the new generation, binary, or config is installed and active, not hand-testing interactive behaviour on every host; report what was exercised where and let John judge. If a host is unreachable or verification fails, the deployment is **partial**: keep the card open, name the pending host/action, and never report it as done. Documentation-only changes need no activation.
- Pi Pocket (`pi-pocket.service`, `docs/pi-pocket.md`) is the production personal assistant.

## Homelab hosts (separate deploy group)

- pi-cielo homelab hosts (Debian; services stay in `~/dev/src/playground/pi-cielo`) run a slim standalone Home Manager profile (`hosts/homelab-common.nix`: Rex server only) as `homeConfigurations."<user>@<host>"`. Currently `pi@pi-01`, `pi@pi-02`, `pi@pi-03`, and `beelink@nas`. Home Assistant is excluded.
- They are not "every host": shared changes don't deploy to them, and `update-system` and the coordinator never touch them. Deploy homelab changes with `mise run homelab-deploy [host...]` from the task worktree (source must contain local `main`); it verifies the active generation and `rex.service`.
- Bring-up (sudo): official multi-user Nix installer, `sudo bash .mise/scripts/homelab-nix-system apply` (idle-priority builds; deploys refuse without it), `sudo loginctl enable-linger <user>`, add the host to `users` in `.mise/tasks/homelab-deploy` and `flake.nix`, deploy, then John opens the tsnet login link from `rex server status`.

## Issue tracking

Use Fizzy only (board from `.fizzy.yaml`; use the CLI's `--jq`). Card commands take the card `number`.

1. Search with `fizzy card list --all --jq '[.data[] | {number, title}]'`. If no card covers the task, create one before repository changes; every task needs a card.
2. Claim it with `fizzy card self-assign <number>` when appropriate. File discoveries with `fizzy card create --board <board-id> --title "..." --description "..."` and link them from the originating card.
3. Add progress and completion comments.

**Closing a card requires John's explicit request or an actual `/wrap` invocation** (its expanded prompt counts; mentioning, quoting, or reading the prompt file doesn't). Outside an active `/wrap`, task completion, deployment, commits, "done", or "wrap up" never authorize closure; inside one, any go-ahead from John does. On `/wrap`, close completed in-scope cards after checking completion and deployment — never blocked or partially deployed work.

## Session completion

1. Update cards and file remaining work; apply the closure rule above.
2. Run only the smallest task-relevant checks.
3. Run `git status` and report staged/unstaged changes.
4. Hand off changes, validation, and next steps, with Mac, Omarchy, Miller, and Drummer deployment status reported separately.

Outside an actual `/wrap`, wrap-up never authorizes a rebuild or `git push`. An actual `/wrap` in this repo deploys per the Deployment section; it never authorizes `git push`. Say `ready to push when you are` only if a local commit exists and push is the only remaining step; otherwise `ready to commit when you are`.
