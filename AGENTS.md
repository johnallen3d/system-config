# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Task scope

- These repository workflows govern repository and Nix-managed changes. They do not require turning a direct operation on a user-owned external file into repository edits or a worktree.
- Keep John's requested outcome as the scope boundary. Do not add documentation, tests, or source changes merely to make a broader workflow consistent; ask before adding optional work.
- Verify the requested outcome directly. Unrelated or optional checks must not become blockers for an otherwise independent operation.
- All applicable safety, authorization, issue-tracking, and both-host verification requirements still apply to the actual task.

## Minimal checks only — strict policy

- This is a personal system configuration, not a software product requiring a comprehensive test suite. Keep repository-maintained checks to the absolute minimum needed to protect concrete, critical behavior; deletion is the default for redundant, speculative, or low-value checks.
- Do NOT add or expand test files, fixtures, frameworks, harnesses, or test dependencies without John's explicit approval for that specific addition. A feature/fix request, a general validation requirement, or an existing test suite is not approval. First explain the concrete failure being prevented and why a smaller direct check is insufficient; if approval is absent, do not add it.
- Do NOT add tests that assert the wording, formatting, or presence of agent instructions, prompts, documentation, or policy clauses. Such assertions do not demonstrate agent compliance. Review these changes directly; do not write a test to enforce this policy.
- Ordinary Nix evaluation, package builds, activation, and runtime behavior MUST NOT depend on this repository's `tests/` directory or repository-maintained validation scripts. Keep any essential retained checks explicit and opt-in, separate from the deployment path. Do not evade this rule by relocating or inlining the same checks into production modules/scripts. Upstream packages' own build checks are not a reason to add repository-owned checks.
- Do NOT run the whole test directory, a broad suite, or unrelated checks by default. Use only the smallest relevant check that directly proves the requested outcome. Do not turn an optional check failure into unrelated debugging, dependencies, or additional deliverables.
- Every retained check must have a concrete, critical failure it detects that is not adequately covered by Nix's existing validation or a smaller direct check. Historical existence, coverage targets, and agent workflow conventions are not justification. If necessity is unclear, ask John rather than adding or preserving scope by default.
- Preserve required safety, authorization, deployment coordination, and per-host outcome verification. Meet those requirements directly and proportionately; they do not authorize a new test suite or instruction-text assertions.

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

- macOS: `mise update-system` updates inputs once, then applies **Mac and Omarchy in parallel**. `--switch-only` skips input updates; `--picker-only` updates only the shared picker; `--local-only` explicitly skips Omarchy. The task synchronizes integrated local `main` to clean, fast-forwardable Omarchy `main`, then deploys the invoking source (including nonignored uncommitted files) from an automatically cleaned temporary directory backed by pinned Git trees; it never overwrites unrelated remote changes or removes task worktrees, and safely prunes matching legacy deployment worktrees after a recorded activation. Either host failing returns nonzero and reports a partial deployment.
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

## Concurrent deployment coordination

- Concurrent task worktrees are normal. Before planning activation, inspect `mise exec -- python3 ~/.local/share/system-config-deploy/.mise/scripts/deployment_state.py status "$task_path"` on each target host. The host-wide lock reports in-flight ownership; active/pending records bind exact generations to Git source, task branch owners, and reproducible layers. A stale lock description is informational: only the kernel lock means busy.
- `update-system` and `nix-rebuild` hold the Mac lock; the Omarchy worker holds its host lock through source preparation, build, activation, verification, and provenance recording. Wait/retry rather than bypassing locks. Manual Home Manager activation must use the same coordinator (see `docs/concurrent-deployments.md`).
- The coordinator automatically carries forward verified already-active task layers and replaces only the invoking task owner's previous layer. It composes source from integrated local `main` into a temporary directory, using pinned Git trees/private indexes without commits, deployment branches, or task-branch merges. The lock owner cleans temporary source after its children exit; durable provenance does not depend on that directory. Never collect every dirty worktree or add an unactivated task.
- Composition is deliberately file-level: identical edits coexist, different edits to the same file (including `flake.lock`) stop with paths and owners, even if a textual merge might succeed. Changes already present in `main` are absorbed; overlapping newer main changes stop. Investigate precise conflicts/uncertain ownership yourself; ask John only for a genuine decision or new authorization, not routine preservation.
- Missing/drifted provenance blocks activation. Bootstrap/adoption requires verified ownership and an exact evaluated-output match to the installed generation. Do not guess from timestamps, build success, or task proximity; do not overwrite existing receipts. Out-of-band rollbacks must be reconciled explicitly. See `docs/concurrent-deployments.md`.
- Carrying active layers is deployment-only preservation, not permission to commit, merge, rebase, push, delete worktrees, restart active agents, activate pending work, or close cards. Report per-host outcomes and retain partial deployment records.

## Shared Mac/Omarchy deployment

- Before changing shared agent, project-context, or user-automation config, identify which hosts import it. Unless John explicitly requests a single-host change, changes shared by Mac and Omarchy must be applied and verified on **both**; a Mac rebuild is not an Omarchy deployment.
- Authorized deployment includes clean, guarded fast-forward synchronization of Omarchy's `main` to reviewed, already-integrated local `main`; do not ask for separate merge permission for this step. Stop on dirty source, divergence, conflicts, or uncertain ownership. This exception does not authorize task-branch integration, new commits, rebases, pushes, or worktree removal.
- For shared Nix-managed configuration changes, use `mise exec -- system-config-deploy "$task_path" --switch-only`, including for older task worktrees whose own scripts predate coordination. Current task tooling also supports `mise update-system --switch-only` from the verified Mac task worktree; it also builds/activates Omarchy's standalone Home Manager configuration. Use `mise run nix-rebuild --switch-only` only for an explicitly Mac-only deployment. The manual Omarchy procedure in `docs/omarchy-agents.md` remains available for Linux-only changes/recovery. Do not run macOS tasks on Omarchy.
- Omarchy deployment source is captured in its `~/dev/src/system-config` Git object database, then materialized in an automatically cleaned temporary directory; no deployment/transport worktree is created. The former `system-config-poc` and `system-config-amfaro` paths were retired; recovery archives are not deployment sources. Keep Omarchy's local `main` synchronized with reviewed, integrated Git history, then compose temporary deployment source from that `main` and verified active layers. Do not copy newer source over an old checkout without advancing its recorded history. Inspect source, lock, worktree ownership, and installed state; transfer only intended changes after checking divergence. Preserve unrelated remote edits and credentials; stop and report conflicts rather than overwriting them. Pi Pocket (`pi-pocket.service`, `docs/pi-pocket.md`) is the production personal assistant; Hermes was removed (#906).
- SSH connects as `johna@omarchy`; its login shell is Fish. Run Bash scripts explicitly with `bash -s`, and use `mise -C ~/dev/src/amfaro exec -- ...` for noninteractive work-profile commands. Use absolute script paths when `mise -C` changes the working directory.
- Verify installed config and effective profile/runtime behavior independently on each host, not just source files or build success. Do not restart active agents or Herdr servers merely to refresh environment; report any required agent restart explicitly.
- If a host is unreachable, synchronization is blocked, or verification fails, the shared deployment is **partial**. Keep its Fizzy card open and name the pending host/action in the handoff. Never report unqualified "applied", "done", or "ready to push" while deployment remains pending.
- Documentation-only changes do not require activation. Keep these deployment instructions available in Omarchy's Git-based deployment source too.

## Issue tracking

Use Fizzy only—no Markdown TODOs, other trackers, or duplicate cards. The project board is selected by `.fizzy.yaml`. Use the CLI's built-in `--jq` for programmatic output.

1. Check existing work with `fizzy card list --all --jq '[.data[] | {number, title}]'` and search before creating a card. If no card covers the current task, create one before starting repository changes; every task needs a card, and `/wrap` must not finish with untracked work.
2. Claim the task's card with `fizzy card self-assign <number>` when appropriate.
3. File discoveries with `fizzy card create --board <board-id> --title "Title" --description "Context"` and relate them in the originating card's description or comments.
4. Add progress/completion comments; leave cards open unless John explicitly requests closure directly or actually invokes `/wrap`. Only then may you run `fizzy card close <number>` within that authorization's scope.

**Card closure requires John's explicit authorization.** Task completion, successful deployment, committing, ordinary session-ending language (including "wrap up" or "done"), and merely mentioning/quoting `/wrap` do not authorize closure. An actual `/wrap` invocation authorizes closing only completed cards within its scope, never blocked or partially deployed work. Without that authorization, report completion and keep the card open; no workflow, example, breadcrumb, or move to the `done` column overrides this rule.

Card commands use the card `number`, not its internal ID. Use board columns for workflow state and tags for type or priority when useful.

An actual `/wrap` invocation includes the command's expanded user prompt. On that invocation, you MUST close completed, in-scope cards after checking completion and deployment; do not misclassify the expanded invocation as a mere mention or quotation. Reading a prompt file through tools is not an invocation.

## Session completion

1. File remaining work and update issue comments. Keep cards open unless John explicitly requests closure directly or actually invokes `/wrap`; apply the closure authorization and scope rules above.
2. Run only the smallest necessary, task-relevant checks under the strict minimal-checks policy above; no blanket test-suite requirement.
3. Run `git status`; report staged/unstaged changes.
4. Hand off changes, validation, and next steps. For shared config changes, report Mac and Omarchy deployment/verification status separately, including pending activation or agent restarts.

Wrap-up alone never authorizes a rebuild or `git push`. Say `ready to push when you are` only if a local commit exists and push is the sole remaining step; otherwise say `ready to commit when you are` or simply hand off.
