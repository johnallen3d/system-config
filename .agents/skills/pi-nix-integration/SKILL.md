---
name: pi-nix-integration
description: Manage Pi packages, skills, themes, and profile configuration in this Nix/Home Manager repository.
---

# Pi Nix integration

## Ownership and profiles

- Package declarations: `modules/home-manager/pi/packages.nix`.
- Latest-upstream Nix launcher and first-run bootstrap: `modules/home-manager/packages/pi.nix`.
- Settings, personal native MCP, and prompt instructions: `modules/home-manager/pi-settings.nix`.
- Shared/local extensions and themes: `modules/home-manager/pi-extensions.nix` and `modules/home-manager/pi/`.
- Refresh owner: `.mise/tasks/harness-refresh` and `.mise/scripts/pi-refresh`.
- Personal: `~/.config/pi`; work: `~/.config/pi-work`; Telegram notes: `~/.config/pi-notes`.

Always respect inherited `PI_CODING_AGENT_DIR`. Use plain `pi`; no named profile launchers exist. For noninteractive work commands, use `mise -C ~/dev/src/amfaro exec -- ...`. That directory selects both Pi and Claude work profiles. Never copy credentials or sessions between profiles or hosts.

Pi stores npm packages under the selected profile's `npm/node_modules`, not the legacy global `~/.local/lib/node_modules`. The launcher tracks first-run bootstrap with `<profile>/packages-installed`; do not delete markers merely to update packages. Bootstrap failure reporting is tracked separately in Fizzy #693, and the Mac's explicit-profile/mise Node-shim edge case in #715.

## Package changes

1. Inspect the active profile with `pi --version` and `pi list`.
2. Add/remove the appropriate `npm:<name>` or `git:<source>` declaration in `modules/home-manager/pi/packages.nix`. Keep shared packages in `sharedPackageSpecs` only when both personal and work need them.
3. Apply unchanged inputs on Mac with `mise update-system --switch-only`.
4. For shared changes, inspect Omarchy's actual `~/dev/src/system-config-amfaro` snapshot, check divergence, transfer only intended files, then build/activate its standalone Home Manager configuration as documented in `docs/omarchy-agents.md`. A Mac rebuild does not deploy Omarchy.
5. Use `mise run harness-refresh` to refresh both hosts' Pi packages and work Claude plugin. `--local-only` explicitly skips Omarchy; Linux always runs host-local. This updates neither Claude's binary nor Omarchy's Home Manager configuration.
6. Verify installed config and runtime discovery independently on each host. Do not restart active agents automatically. Restart Claude after plugin updates and start a new Pi session to load changed extensions.

`pi install`/`pi remove` are native package operations, but persistent declarations belong in Nix. `pi update --extensions` is Pi's native extension-update command; do not add a competing startup updater. The existing refresh worker also removes a bounded list of retired, unregistered personal npm dependencies; it never prunes arbitrary packages or other profiles.

## Native MCP and prompts

Personal uses Pi 1.x's built-in MCP from `<profile>/mcp.json`, with native codemode exposure by default. Use `/mcp` or `pi mcp list` for connection/sign-in status. Persistent configuration edits belong in Nix, not the store-backed file. Work agent-kit retains its separate MCP integration; do not migrate it as a side effect of personal changes.

Personal instructions go in `APPEND_SYSTEM.md`, preserving Pi's native system prompt. `SYSTEM.md` replaces that prompt entirely. Model/skill frontmatter in `/wrap` and `/pkg-install` still requires `pi-prompt-template-model`; ordinary description/argument templates are native.

## Resources and validation

- Project skills: `.agents/skills/`; profile skills: `<profile>/skills/`; shared user skills: `~/.agents/skills/`.
- Local extension declarations: `modules/home-manager/pi/local-extensions.nix` and profile-specific variants.
- Prompt declarations: `modules/home-manager/pi-prompts.nix`.
- `/reload` reloads extensions, skills, prompts, themes, and context files; `pi --no-extensions` also disables built-in extensions unless explicitly supplied.
- Useful gates: `tests/pi-settings.py`, `tests/coding-agent-profiles.py`, `tests/harness-refresh.py`, and `tests/pi-native-personal.mjs` (see `docs/pi-native-personal.md`).

Follow repository AGENTS.md for apply, issue tracking, quality gates, and two-host handoff. Never run direct macOS rebuild or flake-update commands.
