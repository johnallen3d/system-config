# Omarchy coding agents

Tracked in [Fizzy #692](https://app.fizzy.do/6284043/cards/692), with shared work
footer parity in [#706](https://app.fizzy.do/6284043/cards/706).
Builds on the [standalone Home Manager setup](omarchy-poc.md); this is not NixOS.
For persistent sessions and Mac remote access, see the [Herdr guide](omarchy-herdr.md).
For centralized Codex/Claude/Go credentials and Tailscale client access, see
[the subscription proxy guide](omarchy-subscription-proxy.md). Pi routes stay native until central accounts are provisioned and client selection
is verified. Work Claude Code uses the work proxy as its managed default on both
hosts, with six curated Claude/Codex choices; no separate Claude activation is
needed. Restart existing Claude sessions when convenient to pick up routing.
The pinned official model catalog includes Haiku 5.5, and Omarchy's Nix-managed
Claude Code is pinned to 2.1.295 to support it.

`hosts/omarchy.nix` opts into `modules/home-manager/coding-agents.nix`, without
importing the Mac's shell/desktop configuration. Pi uses the same Nix-managed
latest-upstream wrapper and package declarations as the Mac. Claude Code uses the locked nixpkgs packaging with an independently pinned
official release manifest, with its unfree allowance limited to that package.
Nix Node/npm, Git, Python, ripgrep, and uv are available to agent subprocesses.
For `Disk quota exceeded` errors or large Rust builds on Omarchy, see the
[temporary-file quota and recovery guide](omarchy-tmp.md).
Pi exports `SHARP_IGNORE_GLOBAL_LIBVIPS=1` so package installation uses Sharp's
bundled binaries rather than attempting a source build against Omarchy's system
libvips. This is required for the work kit's image/transformer dependencies.

## Profiles

Tracked directory-context ownership in [Fizzy #708](https://app.fizzy.do/6284043/cards/708).
Both Mac and Omarchy manage `~/dev/src/amfaro/mise.toml` through the shared
`agent-projects.nix` Home Manager module. Activation trusts only that managed
config. Its source is `modules/home-manager/agent-projects/amfaro-mise.toml`;
project-specific tools and dependencies remain owned by each project's mise file.

| Directory context | Pi directory | Claude directory |
| --- | --- | --- |
| Personal (default) | `~/.config/pi` | `~/.config/claude-personal` |
| `~/dev/src/amfaro` and descendants | `~/.config/pi-work` | `~/.config/claude-gmatter` |

Use plain `pi` and `claude`. Interactive Fish already activates mise on both
hosts. Changing into an Amfaro project selects **both** `PI_CODING_AGENT_DIR`
and `CLAUDE_CONFIG_DIR`, and clears `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and
`OPENROUTER_API_KEY` for agent execution (not mise's tool installation).
The work context also sets `PI_MODEL_ROUTER_JEV_MODE=primary`; personal contexts
leave the inherited JEV mode unchanged.
Child project configs can override parent values: avoid overriding these profile
variables unless intentional. Named `pi-personal`, `pi-work`, `claude-personal`,
and `claude-work` launchers have been retired.

Noninteractive shells, ordinary SSH commands, and automation must use mise
explicitly; `cd` alone does not activate it there:

```bash
mise -C ~/dev/src/amfaro exec -- claude
mise -C ~/dev/src/amfaro exec -- pi list
```

Bare wrappers respect inherited profile variables. Leaving the work directory
restores the pre-mise environment, which need not be personal if the shell was
started with explicit work variables. Existing agents keep their launch-time
profile: restart in the intended directory rather than changing a running
process's environment. This also applies to `PI_CODING_AGENT_DIR` in Pi sessions.

### Shared work instructions

Edit `modules/home-manager/agent-projects/work-instructions.md` in system-config
for rules shared by all work repositories. `agent-projects.nix` installs the same
content as `~/.config/pi-work/AGENTS.md` and
`~/.config/claude-gmatter/CLAUDE.md`, with Linux-only Omarchy guidance appended.
Neither personal profile receives these rules. Apply shared changes on both hosts
using the deployment procedure below.

Pi reads profile-global and ancestor `AGENTS.md` context (and supports `CLAUDE.md`
as a fallback); Claude Code reads profile-global and ancestor `CLAUDE.md`, not
`AGENTS.md` by default. Profile-global instructions remain available when a
worktree is outside the Amfaro directory, provided both work profile variables are
selected. A parent-directory file alone would not cover that case.

The work policy requires a task-specific linked Git worktree before repository
changes; a feature branch in the primary checkout is not sufficient. Create new
worktrees from `main`, using a simple kebab-case slug: `add-xyz-feature` becomes
`<repository>/.worktrees/add-xyz-feature` on branch `feature/add-xyz-feature`.
The `feature/` prefix applies to every task, including fixes and chores. Keep
work repositories beneath `~/dev/src/amfaro` to retain mise context in their
`.worktrees/` descendants. These are agent instructions, not a write-blocking
hook. Restart existing work agents to load the new context; do not restart them
automatically. Verify through work-profile
`mise exec` with `python3 tests/work-agent-instructions.py --installed --pi-loader
/path/to/installed/pi-coding-agent/dist/core/resource-loader.js` and the installed
profile test (`python3 tests/amfaro-mise.py --installed`). The loader path must be
from that host's actual Pi runtime, not a copied runtime or a model call.

John currently has no personal Claude account. The personal Claude profile stays
installed but dormant; this is intentional, not an authentication failure. Use
Claude from an Amfaro directory for work and Pi from a personal directory for
personal work. No credentials are copied between profiles or hosts.

The retired Pi Claude Bridge integration is not installed. Personal Claude Code
must not silently fall back to work credentials.

Pi settings, package declarations, themes, extensions, prompts, Claude subagent
roles, keybindings, and ELI5 output style are shared with the Mac. Linux gets a
host-appropriate `/pkg-install` prompt. Personal Pi uses native Pi 1.x MCP
(`~/.config/pi/mcp.json`) and `APPEND_SYSTEM.md`, preserving the native system
prompt; work agent-kit's MCP and work `SYSTEM.md` are unchanged. See the
[personal Pi cleanup audit](pi-native-personal.md) for decisions and runtime tests.
Pi configuration is regenerated on each activation, preserving only
`lastChangelogVersion`; persistent changes belong in
Nix. Mac-only legacy extension links, Keychain commands, and Mac-local
Headroom MCP/calc endpoints are not enabled here. The Mac usage footer
is also excluded because its native credential fallback reads across Pi profiles.
The shared proxy quota helper is available without downloading upstream tokens.
Cloudflare MCP is work-only; personal Pi does not declare or require it. Remote MCP endpoints
still require their own login or environment credentials; no Mac tokens are
transferred. Session-capture's Obsidian journal integration requires a separately
configured local vault; this setup does not install Obsidian. The helper writes
daily notes directly and does not require Obsidian to be running or its CLI.
Without a configured vault, automatic capture defers quietly and retains summaries
in `~/.local/state/pi-session-capture/pending` for later replay. Manual
`/log-session` and `/log-issue` attempts explain the missing configuration; real
note read/write failures still warn with the underlying error. Configure
`PI_SESSION_CAPTURE_VAULT_PATH` with the local vault path, or register the vault
in Obsidian's configuration (`Personal` by default, overridable with
`PI_SESSION_CAPTURE_VAULT`). Omarchy now defaults to its Syncthing-paired
`/home/johna/notes` vault through the host declaration and Pi launcher, including
noninteractive launches; an explicitly inherited path still wins. See
[the Syncthing guide](omarchy-syncthing.md#pairing-and-vault-capture). Existing Pi
sessions need `/reload` or a new session to pick up helper changes, but must be
relaunched to receive launcher environment changes.

The shared `pi-headroom` extension **is** enabled for both Pi profiles. It
installs and manages its own local proxy in `~/.pi/headroom-venv`, independently
of MCP configuration. Omarchy's Pi launcher supplies Nix C++ and zlib runtime
libraries through process-scoped `LD_LIBRARY_PATH`; otherwise native Python
wheels can fail with `libstdc++.so.6` missing and the extension only reports
“proxy offline.” This does not change the login shell or Claude environment.
After launcher changes, restart Pi in the intended directory (or retry
`/headroom on` if its process already has the corrected library path).
Verify with `python3 tests/headroom-omarchy.py`; it tests both installed profiles
on isolated ports without model calls or touching an active agent's proxy.

Authentication files and sessions remain writable, machine-local, and outside
Home Manager. Existing `~/.pi/agent` and `~/.claude` data are **not** migrated.
Claude defaults are seeded without overwriting user-owned keys, except for the
Nix-managed work UI: ELI5 output style and the same `agent-kit` status/footer as
the Mac. The footer resolves the registered user plugin within the selected
`CLAUDE_CONFIG_DIR`, using Nix-provided Node, jq, and Git. It remains blank if the
plugin is not installed; no other profile's plugin or credentials are used.
This Claude footer is separate from the excluded cross-profile Pi usage footer.
No personal credentials, cached plugins, or sessions are shared with work.

## Claude startup context

The [Mac/Omarchy context audit](claude-context-audit.md) (#726) found that the
Mac's user-owned native-tool/skill trimming is not shared with Omarchy. Matched
fresh requests measured about 14k tokens on Mac versus 35k on Omarchy; a
temporary Mac context-policy overlay reduced Omarchy to about 13k. These are
absolute input counts including cached tokens, not context-window percentages.
The shared work-context policy from #731 **replicates Mac’s approximately 14k
footprint on both hosts**, as explicitly requested by John. It is declared in
`modules/home-manager/claude-work-context/policy.json` and atomically merged by
Home Manager: Mac’s 31 tool-name denies, 10 named skill overrides, bundled skills
disabled, automatic memory/autocompact/channels disabled. The question/plan/worktree,
notebook, scheduling, messaging, workflow, and selected connector exclusions match
Mac intentionally. Core coding tools and agent-kit remain available.
Existing host restrictions, saved model/window choices, routing/hooks, personal
settings, and credentials are preserved. The conservative 31k policy was rejected
and superseded. Final installed-runtime measurements: **Mac 14,038; Omarchy 13,410**.
See the [full policy and measurements](claude-context-audit.md#reviewed-work-context-policy-731).
`tests/claude-context-audit.py --live` explicitly measures inference;
`tests/claude-work-context.py` tests regressions offline and verifies installed
settings with `--installed`. Add `--live-report PATH` to gate the ~14k footprint.
Start a new work Claude session to load the full policy; do not restart active agents.

## Apply

### Shared changes require two deployments

For agent configuration shared by Mac and Omarchy, apply and verify both hosts
unless the request explicitly targets only one. The Mac's
`mise update-system --switch-only` does not activate Omarchy. A commit or push
also does not refresh Omarchy's current `~/dev/src/system-config-amfaro`
working-tree snapshot. Before building there, inspect its source and installed
state, check for divergence, and transfer only the intended changed files;
preserve unrelated edits and all machine-local credentials.

Ordinary SSH commands use Omarchy's Fish login shell. Execute Bash scripts with
`ssh johna@omarchy 'bash -s'` and pass the script on stdin. For noninteractive
work commands use `mise -C ~/dev/src/amfaro exec -- ...`. Give test scripts
absolute paths because `mise -C` changes the command's working directory, e.g.:

```bash
mise -C ~/dev/src/amfaro exec -- python3 /home/johna/dev/src/system-config-amfaro/tests/amfaro-mise.py --installed
```

Verify installed config and effective profile behavior on each host after
activation. Report the two host statuses separately, plus any agent restarts
required to pick up launch-time environment. Do not silently restart active
agents or Herdr servers. An unreachable or unverified host means a partial
deployment: keep its Fizzy card open and hand off the missing host/action.
Documentation-only changes need no activation.

On Omarchy as `johna`, from the system-config checkout (currently the staged
working-tree snapshot at `~/dev/src/system-config-amfaro`):

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' --out-link result-agents
./result-agents/activate
```

Launchers are linked into `~/.local/bin`, already on Omarchy's PATH, as well as
the Nix profile. Shell startup files are not modified. On first activation,
review existing unmanaged `~/.local/bin/pi`/`claude` and back them up outside PATH
before applying. Do not use forced replacement or Home Manager's blanket backup
flag. Unexpected collisions should fail. Run `hash -r` in an existing Bash shell
if it has cached an old command.

## Account status: available-account setup complete

GitHub access and work-kit provisioning have been completed and verified on
Omarchy. **Do not repeat the installation steps below.** Latest verification:

| Profile | Authentication state |
| --- | --- |
| Personal Pi | Credentials configured for its default OpenAI provider |
| Work Pi | Credentials configured for its default OpenAI Codex provider |
| Work Claude Code | Work proxy client key; central claude.ai login stays on Omarchy |
| Personal Claude Code | Intentionally dormant: no personal account at present |

No further agent-login steps are required for the accounts John currently has.
If a personal Claude account is added later, run `claude auth login` from a personal directory on
Omarchy and approve that account in the browser. This is optional, not a blocker.
Do not copy credential files between profiles or from the Mac.

Shared skills and profile-specific MCP services remain separately tracked in
Fizzy #692; no installation commands need to be repeated.

## Provisioning reference (agent/operator only)

Provisioning, credential-helper configuration, package installation, and testing
are agent/operator work, not a manual checklist for John. Only interactive account
approvals require John.

The work Pi package and Claude plugin both use the private `amfaro/agent-kit`
repository. On a fresh host, configure GitHub access with an authorized account first:

```bash
gh auth login
gh auth setup-git
git ls-remote https://github.com/amfaro/agent-kit HEAD
agent-work-setup
```

`agent-work-setup` checks Git access before installing the work Pi package and
`agent-kit@amfaro` Claude plugin. It is safe to rerun: existing marketplaces and
plugins are updated rather than added again. On Linux, Home Manager does not attempt private
plugin installation during activation. Work prompts that depend on the plugin
will not be ready until this succeeds. The shared Pi wrapper currently tolerates
failed bootstrap installs, so a successful `pi-work --version` alone does **not**
prove the private package installed; use the explicit setup command and check
`mise -C ~/dev/src/amfaro exec -- pi list` and
`mise -C ~/dev/src/amfaro exec -- claude plugin list`.

Do not copy the Mac's credential files to bypass these logins.

Verify actual installation and runtime behavior without model calls:

```bash
python3 tests/amfaro-mise.py --installed
python3 tests/coding-agent-profiles.py
python3 tests/agent-work-kit.py
python3 tests/claude-work-statusline.py --installed
```

Claude may show a dependency-install advisory for the plugin's bundled Pi
package-lock entries. The Claude MCP adapter is dependency-free; the second test
checks its real startup, initialization, and tool discovery. Do not disable
Claude's dependency checks or install arbitrary dependencies to hide the warning.

## Refresh

Tracked in [Fizzy #714](https://app.fizzy.do/6284043/cards/714).

From the Mac's system-config checkout, `mise run harness-refresh` refreshes
**both Mac and Omarchy** by default. `mise update-system --harness-only` does the
same without rebuilding; `--harness-refresh` refreshes both after the Mac rebuild.
The task refreshes personal, work, and notes Pi packages plus the work Claude
`agent-kit@amfaro` marketplace/plugin. It does not update Claude's binary or
activate Home Manager on Omarchy.

[Fizzy #733](https://app.fizzy.do/6284043/cards/733) adds a bounded transitive
npm refresh to this same owner, after each profile's Pi reconciliation succeeds.
It selects production transitive names from the existing locks in that profile's
npm root (including retained inactive packages) and declared Git package roots.
`npm update --save=false --omit=dev --legacy-peer-deps` respects parent dependency
ranges, preserves manifests and direct/pinned package versions, and does not
install Pi's host-provided peers. Direct, dev-only, peer, and linked names are
excluded; undeclared cached Git packages are untouched. A missing/unreadable lock
or failed npm update fails that host's refresh; there is no unbounded fallback,
`audit fix --force`, or startup updater. Audit findings requiring direct-package
or major upgrades need separate review, not forced upgrades here; remaining
agent-kit and Mac legacy notes findings are tracked in
[Fizzy #740](https://app.fizzy.do/6284043/cards/740).

The remote run connects as `johna@omarchy` with noninteractive SSH, executes Bash
explicitly, and selects work context through `mise -C ~/dev/src/amfaro exec --`.
Only the two refresh workers are sent into a temporary directory, cleaned up on
exit. No repository synchronization, config, sessions, or credentials are
transferred; each host uses its own installed profiles and GitHub access.
Per-host success/failure is reported. Both hosts are attempted even if one fails;
an unreachable Omarchy or any package/plugin failure returns nonzero and means
the shared refresh is partial. No agents or servers are restarted automatically.

Use `mise run harness-refresh --local-only` for an explicitly Mac-only refresh.
On Omarchy, run `mise run harness-refresh` from `~/dev/src/system-config-amfaro`;
Linux always refreshes only itself and never connects back to the Mac.

Validate orchestration offline with `mise exec -- python3 tests/harness-refresh.py`
on each host. After a live refresh, use the absolute checkout path with work
context (mise changes the working directory):

```bash
mise -C ~/dev/src/amfaro exec -- python3 "$PWD/tests/harness-refresh-installed.py"
```

The installed test checks each profile's declared npm versions/Git revisions
against upstream, Pi runtime and package discovery, the enabled Claude plugin,
native Sharp processing, and Claude MCP startup/tool discovery without model
calls. It also audits production dependency roots, fails on the stale
brace-expansion advisories, and reports remaining findings separately. It tests
host-local installations, not just source files or marker files.

Pi's runtime follows latest upstream; a new process resolves it through npx.
For a single-profile refresh on either host:

```bash
cd ~
mise exec -- pi update
cd ~/dev/src/amfaro
mise exec -- pi update
mise exec -- claude plugin marketplace update amfaro
mise exec -- claude plugin update agent-kit@amfaro
```

Restart Claude Code after plugin updates. Claude's binary follows the locked
nixpkgs version; update inputs only as a separate requested change, then apply
Home Manager on Omarchy. Do not run the repository's macOS rebuild tasks here;
`update-system` rejects rebuilds on Linux (`--harness-only` is safe and host-local).

## Rollback

Keep the previous Home Manager generation path before applying. Its `activate`
script restores managed packages/files without uninstalling VNC or Nix. Original
mise wrappers are saved at `~/.cache/coding-agents/legacy-launchers` during the
initial deployment; after rolling back (which removes managed launcher links),
they can be restored to `~/.local/bin`. Runtime profile data are intentionally
retained and must not be deleted as part of rollback.
