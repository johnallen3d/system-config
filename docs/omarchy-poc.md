# Omarchy: standalone Home Manager proof of concept

Tracked in [Fizzy #688](https://app.fizzy.do/6284043/cards/688).

The results below describe the original isolated POC. The current host profile
also manages an opt-in [VNC user service](omarchy-vnc.md),
[work/personal coding agents](omarchy-agents.md), and [Fish shell](omarchy-fish.md).
Uninstalling the whole Home Manager profile would remove that service too;
do not repeat the
POC teardown on a host with additional managed resources unintentionally.

Host: Omarchy 4.0.4 (Arch-based), `x86_64-linux`; SSH: `johna@omarchy`;
home: `/home/johna`. This is not a NixOS conversion.

The `johna@omarchy` flake output imports only `hosts/omarchy.nix`, not the
shared package/dotfile suite. It installs Nix-managed `jq` and the Home Manager
CLI, and links `~/.config/nix-home-manager-poc/status.json`; the current profile
also opts into the agent, VNC, Herdr and Fish modules linked in this guide.
Home Manager also creates its profile/session-variable support and XDG `.keep`
placeholders.
The original POC excluded shell configuration and user systemd management;
the current profile opts into Fish and selected user services. Bash startup,
Hyprland, Omarchy themes, GPU integration and MIME databases remain excluded.
Arch's `/usr/bin/jq` remains installed; use the explicit Nix profile path below to prove ownership.

## Verified outcome

Live testing on Omarchy succeeded with Nix 2.35.2:

- Native build, activation dry-run, activation, and repeat activation passed.
- Profile `jq` resolves into `/nix/store`; Arch's `/usr/bin/jq` still works.
- A second generation changed the test marker; reactivating the first restored it.
- Home Manager uninstall removed the marker, POC executables, and XDG placeholder
  links; reactivation successfully restored the original POC.
- All 25 recorded shell/desktop file fingerprints remained unchanged, including
  after the Nix bootstrap. The flake lock and host module were also unchanged.

The original POC was restored after testing. This proves standalone user-level
package/dotfile management on Omarchy, not GUI/GPU or full-system management.
Application configuration and package compatibility outside this scope still
need their own testing.

## One-time Nix bootstrap (interactive sudo required)

Run on Omarchy, as `johna`, not root:

```bash
ssh -t johna@omarchy
sh <(curl -fsSL https://nixos.org/nix/install) --daemon --no-channel-add --no-modify-profile
```

The official multi-user installer adds `/nix`, build users, the Nix daemon,
`/etc/nix/nix.conf`, and global shell integration. `--no-modify-profile` is not
a guarantee against global `/etc` changes; the Home Manager POC itself does
not manage shell startup files. Review the installer's plan before confirming.
Do not grant passwordless sudo just for this POC.

The original experiment's working-tree snapshot was retired on 2026-10-12;
`~/dev/src/system-config-poc` no longer exists. Its unchanged recovery copy is at
`~/.local/state/system-config-retired/20261012T191329Z/system-config-poc`, with
verified file hashes and separately retained Nix result roots alongside it.
Do not activate this historical copy. The pre-install shell/desktop fingerprint
remains at `~/.cache/nix-home-manager-poc/baseline.sha256`.

The later non-Git deployment snapshot was also retired on 2026-10-12 at John's
explicit request. `~/dev/src/system-config-amfaro` no longer exists and has no
compatibility symlink. Its unchanged recovery copy is at
`~/.local/state/system-config-retired/20261012T192019Z/system-config-amfaro`, with
verified file hashes and separately retained Nix result roots alongside it.
Neither archive is an active deployment source; do not activate either archive.

Source consolidation is tracked in [Fizzy #781](https://app.fizzy.do/6284043/cards/781).
Deployment source now belongs to the normal `~/dev/src/system-config` Git
repository. The recovered deployed version is in its linked worktree
`.worktrees/consolidate-omarchy-config` on `feature/consolidate-omarchy-config`;
the stale primary checkout's independent uncommitted changes remain untouched.
The recovered build preserves exact installed Hermes metadata and unit bytes,
including the three historical bytecode artifacts in its approved fileset.

The installed Hermes service was not restarted or changed by recovery, but its
approved runtime still hard-codes the removed source path in engineering/final-gate
checks. Those source-dependent operations remain blocked, not bypassed.
[The #780 guard repair](https://app.fizzy.do/6284043/cards/780) was activated from
the recovered Git worktree and the pending personal instructions were verified;
Hermes remained on the same PID/invocation and protected state stayed unchanged.
Unchanged-identity activations may pass that guard; changed Hermes code, restart
or engineering operations require the reviewed lifecycle. See the
[current Git-based deployment procedure](omarchy-agents.md#apply).

## Build and apply on Omarchy (no sudo)

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
cd ~/dev/src/system-config/.worktrees/consolidate-omarchy-config

# Activate only when the guard approves unchanged live identity; no restart permission.
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result
./result/activate
```

A fresh clone can use the same commands from its own checkout after these
changes are committed. No lock update or separate Home Manager channel is
needed. Do not use `-b backup` or force file replacement: unexpected collisions
should stop activation instead of overwriting Omarchy configuration.

## Verify and repeat

```bash
jq_bin=$(readlink -f "$HOME/.nix-profile/bin/jq")
case "$jq_bin" in /nix/store/*/bin/jq) ;; *) exit 1 ;; esac
"$HOME/.nix-profile/bin/jq" --version

test -L "$HOME/.config/nix-home-manager-poc/status.json"
"$HOME/.nix-profile/bin/jq" -e \
  '.host == "omarchy" and .managedBy == "home-manager" and .scope == "isolated-cli-poc"' \
  "$HOME/.config/nix-home-manager-poc/status.json"

# Reapplying the same generation must succeed without creating conflicts.
./result/activate

# Compare the original shell and desktop file list and contents.
{
  sha256sum "$HOME/.bashrc" "$HOME/.bash_profile"
  find "$HOME/.config/hypr" "$HOME/.config/omarchy" -type f -exec sha256sum {} +
} | sort > /tmp/omarchy-poc-after.sha256
cmp "$HOME/.cache/nix-home-manager-poc/baseline.sha256" /tmp/omarchy-poc-after.sha256
```

The shell features flag above affects only this session. Home Manager does not
source its generated session variables because it does not own Bash here.

## Prove rollback

On the disposable snapshot only:

```bash
initial_generation=$(readlink -f result)
cp hosts/omarchy.nix /tmp/omarchy-poc-host-original.nix
sed -i 's/isolated-cli-poc/isolated-cli-poc-v2/' hosts/omarchy.nix
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result-v2
./result-v2/activate
"$HOME/.nix-profile/bin/jq" -e '.scope == "isolated-cli-poc-v2"' \
  "$HOME/.config/nix-home-manager-poc/status.json"

"$initial_generation/activate"
"$HOME/.nix-profile/bin/jq" -e '.scope == "isolated-cli-poc"' \
  "$HOME/.config/nix-home-manager-poc/status.json"
cp /tmp/omarchy-poc-host-original.nix hosts/omarchy.nix
```

## Remove Home Manager's POC resources

This host had no previous Home Manager profile. If that changes, do not
uninstall another configuration. Resolve the locked sources explicitly so
uninstall does not require channels:

```bash
nixpkgs_path=$(nix eval --impure --raw --expr \
  "(builtins.getFlake \"path:$PWD\").inputs.nixpkgs.outPath")
hm_path=$(nix eval --impure --raw --expr \
  "(builtins.getFlake \"path:$PWD\").inputs.home-manager.outPath")
"$HOME/.nix-profile/bin/home-manager" \
  -I "nixpkgs=$nixpkgs_path" -I "home-manager=$hm_path" uninstall

test ! -e "$HOME/.config/nix-home-manager-poc/status.json"
test ! -L "$HOME/.config/nix-home-manager-poc/status.json"
```

Confirm the uninstall prompt. Nix itself, cached store paths, generation
history, and this source snapshot remain; this is not a Nix uninstaller.

## Current native Hermes ownership (#763)

Native Omarchy became independently verified **NATIVE_LIVE at
2026-10-11 13:22:55.731199 UTC** under
[#763](https://app.fizzy.do/6284043/cards/763), parent
[#756](https://app.fizzy.do/6284043/cards/756). Initial accepted generation:
`/nix/store/gcsdvmj7dmi1d3kwpqi6z3xcl25w0hxg-home-manager-generation`.
Production metadata is `/home/johna/.config/hermes-native/production.json`;
`runtime.json` and `staging/baseline-0.21.2` remain separate inactive staging.
Native has the sole poller/authoritative gateway and enabled zero-model NY05 brief.
NAS is protectively stopped/PID0/restart-disabled, with managed redeployment blocked.

**Initial live is not final acceptance:** the next distinct brief is
2026-10-12 05:00 America/New_York (09:00 UTC); at least 24-hour observation
including that brief is pending, earliest boundary 2026-10-12 13:22:55.731199 UTC.
Retain recovery assets at least 14 days, with no deletion or automatic restore.
The four successful acceptance receipts and accepted journal were retained;
no completed probe/inbound/canary/brief/send was repeated, and no restore/reimport
occurred. Ordinary writers retain the existing NAS-style same-file nonoverlap,
shared helper-lock/atomic/readback and local Syncthing conflict-stop policy;
normal writes/daily briefs require no fresh global human lease. Existing service
restart/sleep/logout/linger policy is unchanged. The authoritative cross-project
runbook is pi-cielo's `docs/hermes-native-operations.md`.

The #755–#762 sections below are **historical preparation checkpoints**, not
current NAS ownership or instructions to repeat completed cutover/acceptance.
For the later Home Manager stop, approved recovery, and activation guard, see
[Hermes activation lifecycle](hermes-activation-lifecycle.md) (#771). Never use
historical generations as automatic rollback or restart targets.

## Native Hermes foundation (#755)

[Fizzy #755](https://app.fizzy.do/6284043/cards/755) opts Omarchy into
`modules/home-manager/omarchy-hermes.nix` with `nativeHermes.enable = true`.
This is **isolated staging**, not production cut-over. NAS remains the sole
production gateway and morning-brief owner until
[#763](https://app.fizzy.do/6284043/cards/763). No containers, container runtime,
NixOS conversion, desktop changes, credentials, NAS state transfer or real-vault
integration are installed by this foundation.

### Installation and mutable-path contract for #757/#758

- Native Hermes **0.21.2**, upstream revision
  `a19160bbf02dc37c57ff47cf0eaa4a3ab8ee43dc`, now matches the NAS source baseline
  inventoried by [#757](https://app.fizzy.do/6284043/cards/757). This replaces the
  initial **0.21.6 / Python 3.14.6** staging foundation: migration must not silently
  include that software upgrade. The unchanged upstream native constructor uses
  sealed `uv.lock` and npm dependencies with the messaging extra. Its legacy
  `python312` parameter and nested `callPackage` are mapped to **Python 3.13.14**
  in a private Hermes-only package scope; host nixpkgs is not overridden.
- The Hermes input retains its independently locked upstream package inputs;
  correcting it must not update existing host inputs. Native uv **0.11.32**, Node
  **26.5.0**, npm **12.0.2**, and SQLite **3.53.3** are the fixed upstream Nix
  lineage, not NAS's downloaded tool/patch versions **0.11.6 / 26.5.1 / 11.17.0 /
  3.53.4** (NAS Python is **3.13.5**). These native differences avoid replacing
  reviewed upstream packaging with custom downloaded binaries or floating inputs.
  Python stays within source's `>=3.11,<3.14`; Node/npm satisfy its declared
  engines. Installed tests verify actual versions, NAS source-manifest hashes,
  package metadata, SQLite's WAL-reset fix floor **3.51.3**, and FTS5 trigram on
  an in-memory synthetic database. This is source-baseline alignment, not full
  dependency/capability parity or a production-state import pass.
- Doctor's PM-only Node lookup may warn that Node is absent even though the
  explicit native binary/PATH passes; browser/PM provisioning and capability
  parity remain later-stage work. Native tooling stays pinned and offline.
- Home Manager owns **`~/.local/bin/hermes-native`**, its Nix profile command,
  `~/.config/hermes-native/runtime.json` (non-secret installed runtime metadata),
  and `~/.config/systemd/user/hermes-native.service`.
- Omarchy's existing **`~/.local/bin/hermes`** mise auto-installer and
  **`~/.hermes`** are third-party/user-owned and remain untouched. Use
  `hermes-native`, never bare `hermes`, for this migration's checks.
- `HERMES_HOME` is `/home/johna/.local/state/hermes-native/staging/baseline-0.21.2`. Mutable
  `config.yaml`, `.env`, sessions, memories, skills, cron state and logs belong
  beneath this directory, **not** in Home Manager symlinks or the Nix store.
  Activation seeds a regular private config and empty `.env` only when absent;
  subsequent activation does not overwrite them. Credentials remain absent at
  this stage; later credential staging is #760.
- Isolated `HOME`: `/home/johna/.local/share/hermes-native/staging/baseline-0.21.2/home`;
  `XDG_CONFIG_HOME`: `/home/johna/.config/hermes-native/staging/baseline-0.21.2`;
  cache/uv cache: `/home/johna/.cache/hermes-native/staging/baseline-0.21.2` and its `uv/` child.
  Working directory/disposable workspace:
  `/home/johna/.local/state/hermes-native/staging/baseline-0.21.2/workspace`.
  Hermes logs are under `HERMES_HOME/logs`; service stdout/stderr use the journal.
  Directories are `0700`, seeded config/environment files `0600`, umask `0077`.
- Launcher and user service have the same explicit environment and pinned PATH.
  The launcher clears inherited provider credentials, vault variables, Python
  search paths and workstation profile state **in its child only**. It does not
  change the caller's `PI_CODING_AGENT_DIR` or `CLAUDE_CONFIG_DIR`, copy either
  profile, or export a global workstation `HERMES_HOME`.

The correction uses fresh **`staging/baseline-0.21.2`** subnamespaces because the
initial 0.21.6 seed is config format **50**, while NAS/0.21.2 is format **44**.
The original staging config/state/cache/HOME are retained, not downgraded or
silently overwritten. #757's read-only inventory describes the earlier paths;
these corrected installed paths supersede that foundation reference for #758.
No private or authoritative state is transferred between these trees.

These are the installed **staging** paths/version aligned with #757's inventory
and compatibility contract. The conservative migration source baseline is now
selected; an upgrade to 0.21.6 is not included or approved. Final production state
namespace, state/schema migration and authoritative managed assets remain gated
by the later migration stages. Do not silently point this runtime at NAS state,
a Syncthing vault or production secrets.
Historical Messages search remains **`UNSUPPORTED_SCHEMA`**; native deployment
neither fixes nor enables it.

### Safety gates and installed validation

The foundation public launcher allows `--version`, `--help` and plain `doctor`.
#758 adds only the fixed `capability-check` described below; it does not expose
arbitrary task/plugin arguments or interpreters. Inference, gateway startup,
cron execution, package repair/update and doctor `--fix`/`--live` remain refused.
No unrestricted upstream `hermes` command is added to the user profile.
`hermes-native.service` has no `WantedBy` or timer, refuses manual starts, and its
launch command is independently blocked. Telegram stays disabled and
CLI/Telegram toolsets stay empty. The #758 overlay mirrors the reviewed search
and macros plugins and registers one **paused** no-agent brief; MCP and production
credentials remain absent. Those assets are not production enablement or full
capability parity.

After standalone Home Manager activation on Omarchy:

```bash
~/.local/bin/hermes-native --version
~/.local/bin/hermes-native --help
python3 -I /home/johna/dev/src/system-config-amfaro/tests/hermes-native.py --installed
```

The installed test resolves the **actual Home Manager generation**, compares
installed metadata/launcher/unit/environment, verifies private mutable paths and
blocked commands, exercises the installed generation's fresh-seed scripts in a
private disposable workspace, and runs CLI/doctor in transient user services with
that same environment. It checks the real closure for container runtimes and reports the
installed Python/uv/Node/npm versions. Plain baseline doctor is expected to return
**0 even with findings** (its summary does not set a failing exit status), with
exactly two numbered findings: deliberately absent model credentials
and its **native-entry-point layout false positive**. In 0.21.2,
`doctor_platform.py` looks for `PROJECT_ROOT/{venv,.venv}/bin/hermes` even when
`PROJECT_ROOT` is the Nix wheel's site-packages directory. The installed test
independently executes the actual Nix venv entry point and wrapped service CLI,
then gates that exact advisory; all other findings fail. No upstream patch,
checkout-layout shim, `pip` reinstall or `doctor --fix` is used. This is not a
fully green or credential-ready doctor. Do not fabricate a key, copy a workstation
login or enable production to hide either expected diagnostic. Its private output is retained at
`HERMES_HOME/logs/foundation-doctor.log`.

### Activation ownership and rollback

**Historical foundation-only recipe:** after #760 imports auth/schema state, the
pre-#760/pre-Hermes rollback examples below are not compatible automatic targets.
Use the receipt-aware #761 handoff at the end of this document instead; never run
generic Home Manager rollback/uninstall against imported staging.

Use the standalone apply command above, without updating host inputs. Before
transferring changes, inspect Omarchy's active `system-config-amfaro` snapshot
and installed generation; preserve its independent lock revisions and unrelated
edits. A local commit/push does not deploy that snapshot. Save the previous
generation, scoped source files and lock before applying. #755 stores those
under `~/.cache/hermes-native/deploy-755-*` (the `deploy-755-current` file records
the latest directory), with `previous-generation` naming the rollback target.
The source-baseline correction's scoped source backup and private evidence are
under `~/.cache/hermes-native/correction-755-*`; `correction-755-current` records
that directory. Its saved earlier 0.21.6 generation is historical staging evidence,
not the selected migration baseline. The corrected 0.21.2 generation also passed
rollback to the original pre-Hermes generation and subsequent repeat activation,
retaining both staging trees without altering unmanaged Hermes, Herdr or linger.

Rollback is reactivation of that **previous generation**, not Home Manager
uninstall, uninstalling Omarchy's Hermes, deleting staging state or stopping NAS:

```bash
backup=$(cat "$HOME/.cache/hermes-native/deploy-755-current")
previous_generation=$(cat "$backup/previous-generation")
"$previous_generation/activate"
```

This removes the new managed launcher/unit/metadata and restores the prior user
profile; writable staging remains for inspection or reactivation. To make the
rollback persistent, restore only the saved scoped source/lock files after
checking for intervening changes, or disable the Omarchy opt-in before the next
build. Do not overwrite later agents' source/state changes or perform destructive
cleanup. Reapplying `result-hermes-native/activate` restores the staged foundation.

The #755 rollback rehearsal restored the saved previous generation and confirmed
that its managed launcher/unit/metadata disappeared while mutable staging stayed
intact. Reactivation and repeat activation passed; unmanaged Hermes/state, Herdr's
PID and linger setting were unchanged. Private evidence is retained in the same
backup directory. Fresh-seed probes remain under the disposable staging workspace.

Existing `Linger=yes` was observed but is not managed or changed here. No reboot,
logout, linger, suspend or uptime policy is changed. Production user-service
lifecycle across logout/reboot/sleep is a later readiness/cut-over decision, not a
reason to start this blocked gateway. No active agent/Herdr restart is required.

## Native managed capabilities (#758)

[#758](https://app.fizzy.do/6284043/cards/758) extends only isolated Omarchy staging.
**NAS remains the unchanged sole production owner. The offline capability port
and guarded installed acceptance below passed; this is not production readiness,
authoritative state transfer, card-closure permission or cutover authorization.**

### Single source and reconciliation contract

`modules/home-manager/hermes-native/` in **system-config** is the sole canonical
native asset source: skills, search/macros plugins, reviewed food helper,
`morning-brief.sh`, proposal exporter, provenance, reconciler and fixed checks.
`pi-cielo/hosts/nas/hermes/` remains NAS source, not a second native installer.
The vault continues to own its existing mise tasks and shared atomic note
helpers; their actual bodies are not permanently forked into this repository.

Home Manager activation runs `reconcile.py` once against the private config-44
namespace. It mirrors only provenance-listed assets, maintains
`HERMES_HOME/managed-assets.json`, preserves unowned skills and unrelated
preferences, and fails closed on linked paths, unexpected mirror drift,
credentials/queues, active jobs or duplicate brief records. Managed policy fields
are overlaid deliberately: empty toolsets/MCP, disabled Telegram, search/macros
plugin discovery, authorization exception strings, secret redaction, low-noise
Telegram display and menu priority. Managed menu names precede existing unrelated
priority entries. Drift is a human-review event, not permission to discard it.
Repeat reconciliation must preserve bytes and mtimes, not just avoid duplicates.
This reconciler is **not** #759's universal production filesystem/write gate.

- `HERMES_NATIVE_ASSETS`: immutable Nix source; do not edit a runtime mirror to
  make it canonical.
- `VAULT_DIR` and `VLT_VAULT_PATH`: exactly
  `HERMES_HOME/workspace/notes`, a disposable staging convention, **never**
  `/home/johna/notes`. `VLT_VAULT=Personal` is the deterministic task argument.
- `HERMES_NATIVE_MISE`: absolute pinned Nix wrapper; task subprocess PATH comes
  only from `HERMES_NATIVE_TASK_PATH`, without user profiles or `/usr/local`.
  `MISE_AUTO_INSTALL=0`, trusted config is restricted to the disposable root,
  and uv is offline with managed-Python downloads disabled.
- Native libraries are Nix closure dependencies; no global `LD_LIBRARY_PATH`,
  copied `/usr/local`, Docker, Podman or s6 hooks are introduced. The exact mise
  release bytes are executed by the pinned Nix ELF loader with explicit library
  paths and `argv0=mise`: auto-patching this release crashed before `--version`.
- `GOG_HOME=HERMES_HOME/gogcli` is a private staging path. The exact reviewed
  Calendar command boundary is retained; `GOG_READONLY=0` does not grant blanket
  writes or provision credentials. #760 must verify effective gog config/keyring
  paths and supported account/provider integration before enabling anything.
- `HERMES_EXEC_ASK=true`, `HERMES_REDACT_SECRETS=true`, Telegram reactions,
  America/New_York timezone and reviewed display/menu policy are retained.
  Telegram credentials and allowed-user identities are **not** copied. Their
  effective integration/auth checks remain #760; no polling or delivery occurs.

### Native tool pins and intentional differences

| Tool | Native staging | NAS inventory |
| --- | --- | --- |
| mise / vlt / gog / Mike Farah yq | 2026.9.7 / 0.11.0 / 0.40.0 / 4.53.6; same release artifact SHA-256 pins | Same releases |
| jq | 1.8.2, locked nixpkgs | 1.8.2 |
| defuddle | 0.19.4, locked native Node closure | 0.19.3 |
| tesseract / libheif | 5.5.3 / 1.23.5, native libraries/data | 5.5.0 / 1.23.4 |
| util-linux (`column`, `flock`, `findmnt`) | 2.42.3 | Debian 2.41.5 |
| curl / CA bundle / sd | 8.22.0 / 3.126 / 1.1.0, explicit native paths | Debian image tooling; sd is a vault-task dependency |

| NotebookLM | `notebooklm-py[browser]==0.8.2`, prebuilt Nix-owned CLI/browser-extra closure | Same contract pin |
| Task Python / PyYAML | 3.13.14 / **6.0.2**, separate from Hermes's PyYAML 6.0.3 | Reviewed PEP723 requirement |
| Pillow / pillow-heif / reportlab / pypdf | 12.3.0 / 1.4.0 / 5.0.0 / 6.14.2 | Native fixture dependency closure |
| Playwright Python / driver+browser / Poppler | 1.61.0 / 1.61.1 / 26.06.0 | Native fixture dependency closure |

These versions supplement the foundation Python/uv/Node/npm/SQLite pins above.
The exact NotebookLM `uvx --from 'notebooklm-py[browser]==0.8.2' notebooklm`
invocation resolves to the prebuilt closure, not a runtime network install. The
reviewed `common-foods-browser` and `scripts/macros-details` PEP723 invocations
use the exact prebuilt task Python closure. Other uv/uvx invocations remain
offline; no Python/browser download is enabled. `HERMES_NATIVE_TASK_PYTHON`,
`PLAYWRIGHT_BROWSERS_PATH`, `NOTEBOOKLM_HOME`, the CA bundle and pinned
`FONTCONFIG_FILE` are explicit in installed metadata and the service environment.
The isolated Chromium renderer crashed without fontconfig; a Nix-owned DejaVu
font configuration fixes this without binding host fonts, profiles or network.
Both fixture namespaces provide their own `/dev/shm`.

The reviewed OCR task still invokes `heif-convert`; libheif 1.23 provides
`heif-dec`. A native compatibility alias preserves its input/output argv. Actual
PNG/HEIC OCR and PDF extraction are tested below, not inferred from versions.
A narrow native mise adapter avoids the reviewed weight helper's identical-retry
blank-line accumulation after successful exact vlt readback. First writes and
changed values still use the actual shared task; wrong stage/root/offline flags
and linked notes are refused. This is disposable-stage compatibility, **not** a
production write/locking gate or a permanent fork of vault task bodies.

### Live drift and private inputs

Provenance records reviewed live NAS hashes without publishing private skill
contents. The direct zero-model macros plugin is based on the **enabled live**
plugin, not an inferred replacement by the macros skill. Search retains argv-only
execution, credential-free children, ten-second timeout and fixed-width capped
output; macros retains fifteen-second timeout and unchanged successful stdout.
Both handlers refuse operation outside their offline disposable gate.

The live food helper supports correction **and removal**, strict selection,
retry no-ops and shared vault locks. The native adaptation fixes a reviewed bug
that could consume a following top-level Tasks section during totals replacement;
NAS is untouched. Actual writer/helper CLI, totals, atomic replacement, vlt
readback and identical-retry/removal fixtures pass. John selected **preserve NAS
behavior**: `/food` is now installed with transparent best-effort estimates when
only nutrition is absent, deterministic known values preferred, and explicit
food/date/meal/amount required (otherwise clarify, do not write). No production
writer or external lookup permission follows from this policy choice.

John approved preservation of all six private custom skills and three companion
files. All nine files were fully reviewed; no NAS-only absolute path replacement
was needed. Relative vault paths remain intact. Private contents are **not** in
Git or the world-readable Nix store. They are staged as private user-owned runtime
state at `/home/johna/.local/state/hermes-native/private-skills-staged/baseline-0.21.2`
(directories 0700, files 0600), outside `HERMES_HOME/skills`. The private
`native-review.json` records hashes and each enabling gate. Actual discovery,
hyphen/underscore aliases and reconciliation preservation pass only in the
isolated disposable fixture; host registration remains disabled.

| Private skill | Enabling gate (not satisfied by discovery) |
| --- | --- |
| macro-aware-meal-planning | #759 private-vault read confinement |
| obsidian-dashboard-integrity | #759 write/trash/conflict confinement; rendered Obsidian check |
| calendar-note-reconciliation | #759 vault write/readback; #760 authenticated Calendar |
| personal-daily-operations | #759 write/readback; #760 reminder delivery; managed explicit food-portion policy prevails |
| shopping-research | #760 network/provider evidence |
| local-slash-commands | #759 task-write confinement; #760 gateway registration/reload |

Private content is reviewed data, not authority to override authorization or the
managed explicit food-portion policy. Historical Messages remains
**UNSUPPORTED_SCHEMA**, with no enabled MCP or private conversation access.

### Inactive morning brief and proposals

Activation records exactly one `pi-cielo-morning-brief` job: `0 5 * * *`,
America/New_York, `no_agent=true`, empty prompt, **paused / enabled=false**,
`next_run_at=null`, no delivery/failure-delivery target. No timer, `WantedBy`, cron
tick or scheduler create/resume API is used. The fixed check retains a synthetic
mise adapter. The separate operator-only suite executes the actual reviewed
`morning-brief`, shared atomic writer and vlt readback, with
`MORNING_BRIEF_DELIVERY=stdout` and flights disabled. Only weather/calendar
fetch/format providers are synthetic; a delivery sentinel must never execute.
Actual orchestration, unrelated-section preservation, byte/mtime retry no-op,
provider failure before writing and missing-input atomic-writer failure pass.
This does not prove authenticated provider results or scheduled delivery.

The native exporter emits schema **2**, owner **system-config**, with exact
`skills/<group>/<skill>/<file>` to
`modules/home-manager/hermes-native/skills/...` mapping. The pi-cielo reviewer
requires explicit `--target-owner system-config --repo <reviewed-checkout>` and
retains committed-vault provenance, exact approved-commit, hash/base, path and
secret checks; proposed tests remain inert text. Historical schema 1 remains
NAS/pi-cielo-only. No native publication command is exposed: the improvement
skill explicitly gates real proposal writes until #759 and later activation.

### Validation boundaries and next cards

`hermes-native capability-check` is a fixed Nix-owned program in a bubblewrap
mount/network namespace: read-only Nix store, disposable `/tmp` and `/home`, no
production vault, caller profiles or network. No arbitrary script/task arguments
or mutable code are bound into that check. Its synthetic mise adapters prove
native dispatch/environment behavior only. They must not be called external
vault-task parity. Installed validation uses the actual Home Manager generation
and transient service environment via `tests/hermes-native.py --installed`.

The operator-only `tests/hermes-native-vault.py` accepts only privately staged,
allowlisted **task code** (17 files with verified hashes) and the nine reviewed
private skill files read-only. Its fresh mount/network/PID namespaces expose
only the Nix store and these inputs; `/home` and `/tmp` are disposable, and
`/home/johna/notes`, profiles and credentials are absent. Private source contents
are never returned as diagnostics. This is not an unrestricted launcher route.

#### Actual installed acceptance, 2026-10-10

Final guarded installed generation:
`/nix/store/3pc94d5qffzwhfg8cnw1jbwz8p13r8kl-home-manager-generation`.
It supersedes the earlier #758 checkpoint above. Immediate candidate diff and
preflight preserved the verified current
`/nix/store/n49wpw039ljwddgdqfbsi5gfr9652qkr-home-manager-generation` rollback
baseline, current Fish completion contents and unrelated home-path binaries,
including the **absence** of the old sidebar links. Nothing was restored from an
obsolete checkpoint. Source and mutable-staging backups were saved privately
under `/home/johna/.cache/hermes-native/`. The remote independent `flake.lock`
SHA-256 remains `5c32321b81968ed568dd8e4075e4bd01b5c8a1cf73694527b719ef8f15ec8f8a`.

`tests/hermes-native.py --installed --vault-sources <private-code-directory>
--private-skills <private-staging-directory>` passed using transient user
services with the **actual installed persistent-unit environment**, not a login
shell or build-only candidate. The verifier checks unit/metadata/launcher/path
consistency, blocked gateway/inference routes, foundation pins, doctor smoke,
fixed capability checks and the operator-only suite. Doctor's expected missing
credentials/native-layout advisory is not green production health.

All **15** operator-only cases passed:

- Native headless vlt path/readback; exact task Python/NotebookLM browser-extra
  imports, pinned CLI/login help and synthetic PDF extraction.
- Defuddle local HTML-to-Markdown extraction/refusal; actual PNG/HEIC OCR/refusal;
  common-food search/show/validate and actual PEP723 HTML writer.
- Actual food writer/totals/readback/retry/refusal, aggregate/itemized tasks,
  direct zero-model search/macros stdout parity, and correction/removal helper
  CLI/atomic replacement/readback/retries.
- Actual activity/retry/invalid-time, weight first-write/changed-value/readback
  plus native identical-retry and negative gates, task/list/daily writes,
  retries and literal argv preservation.
- Recipe renderer/atomic writer/readback with a precomputed plan, retry and
  malformed-plan preservation (**no model call**); actual packaged headless
  Chromium local HTML render/search/clear (**no network/personal profile**).
- Actual zero-model morning-brief orchestration/shared atomic writer/readback,
  retry and failure preservation/stdout-only, with explicitly synthetic providers.
- Six private skills/nine files: actual isolated discovery, both alias forms,
  unknown-skill preservation and repeat reconciliation; host remains unregistered.

Fixed checks separately passed authorization/credential filtering, argv/no shell,
negative search/macros grammar, 10s/15s timeouts/output limits, real display/menu
resolvers, paused-job/DST behavior, proposal export/hash/owner/secret gates,
symlink/drift refusal and unsupported Messages. Repeated **actual activation**
preserved all managed staging bytes **and mtimes**, without duplicate skills/jobs.
Private evidence lives in `HERMES_HOME/logs/installed-758.log`,
`installed-task-fixtures-758.log`, `capability-check.log`, `activation-758.log`
and `activation-repeat-758.log`. Input receipt SHA-256:
`75159d28895e21bede9bbf0e1399cf648708008f9815104d561c569aa18a8b30`.

#759 consumes the exact disposable-path/config contract and must establish real
vault/Syncthing confinement, production read/write/locking policy and safe vlt
configuration before changing these gates. #760 owns supported provider/auth,
Calendar/keyring, NotebookLM authentication and Telegram identity/integration;
it must not borrow workstation profiles. These are deliberately **skipped and
disabled**, not claimed as offline parity. Private skills retain the individual
gates above. #762 readiness and #763 sole production transfer remain unsatisfied.
No production vault writes, polling/delivery, credential import, ownership-doc
switch, routing/lifecycle changes or NAS mutation occurred. #758 stays open;
there are no remaining failed offline cases, commits, pushes or cutover.

## Native vault safety (#759)

[#759](https://app.fizzy.do/6284043/cards/759) establishes **staging safety**, not
production enablement. Final actual installed generation on 2026-10-10:
`/nix/store/fxd7cg1yc4kz0qzw0w0g0ykfxcs3ljsq-home-manager-generation`.
This supersedes the #758 generation for installed operator paths; use the current
`~/.config/hermes-native/runtime.json`, never infer mutable or store paths.
`gatewayEnabled=false`, production vault writes **DISABLED**, no active gateway,
no polling/delivery/timer and the sole paused brief remain unchanged. Mac does
not import this Omarchy-only module; no Mac Home Manager activation is needed.

### Enforceable access and closed operator routes

All supported CLI smoke operations now run inside bubblewrap mount/PID/network
namespaces. They expose only read-only Nix packages and the four explicit private
staging roots; host home, production notes, caller profiles, user sockets and host
processes/network are absent. The user service still refuses manual starts and
its gateway argv is independently rejected. This confines the supported runtime,
not arbitrary commands John deliberately runs outside it as the same UID.

- `hermes-native vault-check`: fixed immutable read probe. Production
  `/home/johna/notes` is bound **read-only** at `/vault-readonly`; all other host
  home paths are absent. A regular journal note is read through native vlt and
  compared privately; no note text or names are printed. The probe verifies the
  actual `ro` mount before testing a non-truncating write-open refusal. Symlink
  targets outside the mounted vault cannot reach host profiles or sockets.
- `hermes-native vault-safety-check`: fixed immutable fixture suite; production
  notes are **not mounted**. Disposable read-only fixtures exercise overwrite,
  create, rename, delete, symlink and hardlink refusal. Exact approval/preimage
  CAS, same-file locks, atomic fsync/replace, readback, retry no-op and conflict
  stop are tested only on synthetic data. No arbitrary task/script/root argument
  or production enable/write/restore route is exposed.
- The same existing installed Syncthing **2.1.3** binary runs three temporary
  fixture processes in a private network/PID namespace, with generated synthetic
  identities, loopback-only addresses and no discovery/relay/NAT. These are not
  host services, a duplicate production instance, or another persistent writable
  vault. They reproduce the observed chain and test actual create/update/delete
  propagation, checksums, zero needed items/errors, overlapping complete versions,
  conflict preservation/stop, and all-peer pause/explicit-authority restore.
  This proves the native binary's isolated behavior, not new production canaries
  or compatibility tests against the actual Mac/NAS binaries.

Production folder configuration, devices, filesystem permissions, existing
Syncthing service and its uptime are untouched. `VAULT_DIR`, `VLT_VAULT_PATH`,
mise trust and task execution still point to the existing disposable staging
fixture. The read-only probe uses ephemeral private HOME/vlt config; it does not
copy workstation config, trust/execute mutable production task code, register
private skills, or set the real vault as the Hermes task cwd.

### Actual topology and production-only gates

Read-only observations: Omarchy's existing folder `notes` is `/home/johna/notes`,
UID/GID 1000:1000, root 0755, sendreceive, watcher enabled, no versioning. It is
paired directly only to the Mac; the Mac pairs to both Omarchy and NAS. NAS's
existing folder maps `/data/notes` to `/mnt/storage/syncthing/notes`. **Do not add a
new pair or duplicate folder to hide this relay topology.** All three reported
idle/100%, zero needed files/directories/symlinks/deletes/bytes and zero pull/folder
errors. The tree has 18 symlinks, 16 resolving outside the vault; read confinement
must not depend on environment variables or the same UID's ordinary permissions.

Initial filesystem scans found two conflict-named **historical daily-note copies
in Obsidian Trash**, not active Syncthing errors. They differed from their current
journal counterparts; filenames alone do not prove unresolved current content.
They were preserved in the verified restricted snapshot. **John then removed
those files himself.** Read-only checks verified both artifacts absent on Mac,
Omarchy and NAS, all peers idle/100% with zero needs/errors/conflicts/temporary
files, and both canonical journals unchanged by hash on Omarchy. The Trash
directory currently exists, but neither artifact remains. This issue is settled;
there is no pending artifact-remediation decision. #759 did not rename, delete,
move, reconcile, restore or recreate production files. No blanket Trash exclusion
or hash exception was installed, and John's removal does not enable Hermes writes.

An idle/100% result is only a local/all-index convergence observation, never a
distributed writer lock or global quiescence. `status` exits 2 for a local STOP;
exit 0 means **LOCAL-ONLY**, not permission to write. Production writes remain
unconditionally disabled in installed metadata and the closed runtime routes.
#760 credential staging and #762 isolated rehearsal may proceed with those gates;
production write-readiness/ownership remains a later go/no-go prerequisite.

### Snapshot and restore evidence

A fresh private snapshot was taken without pausing production synchronization or
writers. Source manifests before/after the copy matched; all files, directories,
link targets, modes, owner/group, nanosecond mtimes and xattrs matched the copy and
an independently copied disposable restore. Symlinks were preserved as
inert metadata, never followed; special files are refused. Root restriction 0700
and manifests/receipts 0600 hide original copied modes and all private names/data.

- Snapshot namespace:
  `/home/johna/.local/state/hermes-native/vault-snapshots/snapshot-759-wwe3tv91`.
- Entries: **1479**; manifest SHA-256:
  `52cc5f45a24ea851c75d882b3080ecbcdd2569573b5b93deeb6db4d7ae853012`.
- `tree/`, `manifest.json`, `receipt.json`, `restore-disposable/` are private,
  outside all synced folders, Git and Nix. A later integrity verification passed.
- This is a stable live observation and pre-user-removal recovery copy,
  **not globally quiesced/final authoritative state** or permission to restore.
  Obtain a fresh approved consistent checkpoint before actual write promotion.

### Executable operator checks

On Omarchy, without starting the gateway:

```bash
~/.local/bin/hermes-native vault-check
~/.local/bin/hermes-native vault-safety-check
python3 -I -B /home/johna/dev/src/system-config-amfaro/tests/hermes-native.py --installed

# Resolve the immutable operator and interpreter from CURRENT installed metadata.
python3 -I -B - <<'PY'
import json, subprocess
from pathlib import Path
m = json.loads(Path('/home/johna/.config/hermes-native/runtime.json').read_text())
raise SystemExit(subprocess.call([m['python'], '-I', '-B', m['vaultSafety']['operator'], 'status']))
PY
```

The same metadata-resolved operator supports `snapshot` (new private namespace,
no pause) and `verify-snapshot --snapshot <existing-private-namespace>` (integrity
only). It has **no production restore or enable command**. Never run snapshot
payload scripts, import note contents into Git/Nix, or copy snapshot trees over a
live synced folder. Tests must retain disposable namespaces and no production
canaries, even when a filename gate is locally clean.

### Exact #760/#762 prerequisites and rollback authority

1. Keep this filesystem boundary when staging credentials. Credentials go only to
   the selected isolated roots; never bind host profiles/browser state. Private
   skill registration remains individually gated; a read probe is not permission
   for a skill's write/trash/network/provider operations.
2. Use the vault-owned atomic/workflow helpers, not the synthetic transaction
   test as a permanent task fork. The actual helper passed **eight concurrent
   local writers** under a held stable lock, with every update retained and
   failure preserving bytes/mtime. Its lock lives in `/tmp` and coordinates only
   processes sharing that lock inode. Separate private `/tmp` namespaces and
   other peers do **not** share it. Before production enabling, the vault owner
   must select one writer coordinator/shared lock namespace and an exact per-file
   exclusion protocol; do not assume flock coordinates Syncthing or Obsidian.
3. The per-file reservation must cover NAS gateway/brief, Omarchy Pi capture and
   workstation tasks, Mac Pi/Claude capture/tasks, Obsidian and iCloud/mobile
   editors. Reserve the target on all writers, verify all peers clean, approve the
   exact path/preimage/proposed change, execute the deterministic task, read back,
   then wait for **all three** peers to converge before releasing the reservation.
   A writer that cannot honor the reservation blocks that production operation.
4. Before **production GO**, John must approve the restore coordinator/authority
   and pause order. Isolated #762 preparation acceptance does not supply or require
   inventing that production approval. Recommended authority: Omarchy's verified local checkpoint only
   after separately authorized final writer ownership transfer; do not make NAS
   or Mac authoritative by assumption. A restore requires stopping all writers
   (including Mac's iCloud/mobile path), pausing **all** Syncthing folder peers,
   preserving incident copies, validating a separate restore tree, restoring and
   scanning only the selected authority under reviewed send-only semantics, then
   resuming relay Mac and final NAS peer one at a time. Recheck hashes/conflicts/
   errors before returning to sendreceive and considering writer enablement.
   No production pause, iCloud policy change or restore is authorized by staging.
5. Cross-peer production canaries and actual-binary overlap/restore need explicit
   targeted approval if required by readiness; isolated staging is not blanket
   permission for production mutations. Never auto-delete conflict versions or
   choose a winner by mtime. Any future artifact classification/remediation needs
   an exact owner decision, not a blanket filename exemption; John's two removed
   Trash copies require no further action.

Actual installed full foundation/capability suite, all retained 15 #758 cases plus
this actual local helper contention case (**16 total**), both new namespace
checks, blocked extra argv/write/enable/restore routes, rollback to the fresh
pre-#759 installed generation, reactivation and repeat activation passed.
Managed state **bytes and mtimes**, actual unrelated Fish completion contents,
home-path binaries, absent old sidebar links, independent remote lock and
Syncthing/Herdr PIDs were preserved. Evidence and scoped backups are private under
`/home/johna/.cache/hermes-native/deploy-759-z7_m6vkn`; snapshot/artifact review
receipts contain private paths/hashes only and must not be published externally.
Local source regressions passed; local Python lacks xattr bindings, so xattr
coverage was **skipped locally but passed on actual installed Linux**. The first
candidate's root-file vlt selector and a synthetic newline assertion were fixed;
final installed cases pass. Doctor's two expected findings and unsupported
Messages remain unchanged. No commits, pushes, card closure, NAS modification,
production ownership switch or cutover occurred.

## Restricted state and integration staging (#760)

[#760](https://app.fizzy.do/6284043/cards/760) imports **non-authoritative,
refreshable staging** only. NAS is still the sole running production owner.
The immutable `runtime.json` selects the `baseline-0.21.2` state, isolated HOME,
config/cache and `state-imports` roots. Do not substitute another HOME, profile,
vault, namespace or metadata file. The older config-50 tree stays untouched.

### Imported categories and exclusions

- Seven stores: `state.db`, `shared-state.db`, `kanban.db`, `response_store.db`,
  `runs_idempotency.db`, `cron/notepad.db`, `cron/executions.db`.
- `SOUL.md`, `memories/MEMORY.md`, `memories/USER.md`, `sessions/sessions.json`.
- Only Hermes `openai-codex` provider/token pool; unrelated provider/API-key pools
  are stripped independently by exporter and importer. This is Hermes's own
  canonical auth store, **not** a copied workstation Codex/Claude/Pi login.
- Minimal gog config, encrypted keyring and OAuth client files; no lifecycle locks.
  The only newly provisioned secret is Doppler `notes/prd/GOG_KEYRING_PASSWORD`,
  streamed privately into `GOG_HOME/keyring-password` (0600). Its value never enters
  argv, Nix, Git, diagnostics or shell output. The fixed native read-check loads
  that private file into the gog child environment, matching the existing
  vault-owned task's supported file fallback; production tasks remain vault-owned.
- Minimal NotebookLM `config.json`, `profiles/default/context.json` and
  `profiles/default/storage_state.json` under **isolated HOME/.notebooklm**.
  No browser/workstation profile, cookie-rotation hook or private notebook content.
- Only provider/default model/base URL is merged into config44. All other NAS
  preferences are retained privately for review. Terminal stays local/workspace;
  CLI/Telegram toolsets are empty, Telegram disabled, MCP absent and `.env` empty.

Do not stage Telegram's token yet. Its eventual canonical key is
`NANOBOT_TELEGRAM_TOKEN` at the separately authorized #763 ownership gate. No
`getUpdates`, delivery, bot creation or production Telegram roundtrip is part of
this import. Messages remains **UNSUPPORTED_SCHEMA**, disabled rather than green.

### Snapshot, quarantine and preservation contract

`state-stage.py export` runs as the existing NAS Hermes user, delivered through
stdin (`python -I - export`), without installing source files or restarting the
container. Each SQLite `mode=ro` connection uses the supported online backup API,
including live WAL; **never** copy just the main DB or use `immutable=1` on the
live source. A private temporary backup normalizes only the copy to DELETE journal
mode. Integrity, foreign keys, FTS/trigram integrity, schema30 and message/session
relationships pass. Ordinary selected files and directory membership are checked
again before publishing. This is **per-database consistency, not one globally
coherent source snapshot**; the final authoritative transfer needs a new boundary.

Transport is a direct binary NAS-to-Omarchy pipe, not an archive on the Mac.
The importer consumes stdin using the installed metadata's Python, operator and
explicit environment. No `tar.extract`, payload execution, arbitrary destination
or public import launcher exists. Traversal, links/special files, unapproved code,
wrong ownership, duplicate entries, checksum mismatch and bounds violations stop.

Every import retains original snapshots, manifest, receipt and exact native
preimages in a fresh private `state-imports/baseline-0.21.2/import-760-*` bundle.
Directories are 0700 and files 0600; preimage mode/mtime/UID/GID are also recorded.
First import accepts only config plus the **exact upstream default SOUL and empty
known-table foundation DB**; customized/nonempty preimages are never overwritten.
A receipt verifies later refreshes; target drift, removed imported paths, staged
DB sidecars, or an incomplete CAS transaction stops rather than silently repairing.
Byte-identical refresh preserves payload bytes and mtimes. Originals and old
bundles are retained, never automatically restored, removed or made authoritative.

Queued files, pairing/authorization/routing/control state, source schedules and
scripts, unmanaged macros, six private skills, known skill drift and allowlisted
secondary state stay **quarantined outside discovery**. Five live claim tables
(`gateway_heartbeats`, `compression_locks`, `session_turn_leases`,
`async_delegations`, `delivery_obligations`) are emptied **only in staged state.db**;
all original rows remain in the private source backup. Do not classify every
historical obligation as pending. Durable histories in the other stores remain.
No queue replay, gateway, polling, delivery or scheduling owner is enabled.

### Closed validation routes and operational handoff

```sh
~/.local/bin/hermes-native state-check
~/.local/bin/hermes-native integration-check
```

Both are exact one-argument, Nix-owned routes; extra arguments/URLs/interpreters,
production writes, gateway, chat/inference, `doctor --fix` and arbitrary tasks stay
blocked. State/HOME/config/cache are mounted read-only, host profiles/notes/sockets
and host proc hidden. Only fixed integration checks share networking.

- Provider: canonical Hermes auth-store load and a fixed usage **GET**, no inference
  or token refresh. Codex refresh tokens are single-use/rotation-family protected:
  refreshing a copied NAS grant can break production. Expiry returns
  `EXPIRED_NO_REFRESH_FRESH_EXPORT_REQUIRED` and nonzero, **never auto-refresh**.
  Fresh export/revalidation or an independently approved Hermes login are future
  options, not implied permission to reuse workstation credentials.
- Calendar: supported `gog auth list --check --readonly --json --no-input`, followed
  by `calendar calendars --readonly --json --no-input --max=1` for each of the two
  accounts. Password/account selection is private child environment, not argv.
  gog needs file-keyring locking/access-token caching even for reads: these occur
  only in a minimal disposable **tmpfs copy**, never the staged or NAS keyring.
  The exact inherited Calendar command allowlist is unchanged; no mutation/send.
- NotebookLM: `auth check --test --passive --json` validates storage/JSON/cookies
  and a CSRF/session token fetch; it does not rotate cookies or call a refresh
  hook. This is not browser renewal, notebook enumeration or content upload.
- CLI/doctor: the upstream doctor performs a rolled-back DB write-health probe.
  Therefore public smoke routes copy only minimal state into private tmpfs and
  initialize/probe there; receipt-owned bytes/mtimes stay unchanged. Doctor exit0
  is **not integration health**. Only secret-free semantic summaries are persisted.
  Its missing-API-key advisory can remain with working OAuth; the Nix checkout/
  venv-layout advisory is tested against the actual installed entry point.

The first actual Calendar check correctly failed because the keyring was sealed
read-only; the disposable-copy correction passed both account auth/read checks in
an isolated diagnostic **and the actual installed fixed route in unit environment**.
Provider usage and passive NotebookLM token-fetch checks also passed there. The
inherited disposable Syncthing restore fixture exposed a transient missing-canary
predicate race; only its bounded wait was corrected (absence retries, never counts
as convergence, and persistent absence still fails), with a synthetic regression.
Compatible receipt-aware runtime rollback, reactivation and repeat activation
preserved imported bytes/mtimes/modes. Final installed acceptance is recorded on #760 and under
`/home/johna/.cache/hermes-native/deploy-760-6_lyuxqh`, never in an external artifact.
Real import retained **seven databases, 24 staged payload paths, 32 quarantine
artifacts and five cleared staging-only claim tables**. Receipt/original-snapshot
verification, installed foundation/capability/vault safety and exact retained-bundle
reimport (`changedFiles=0`, payload bytes/mtime preserved) passed. Local synthetic
WAL/import/archive/refusal tests pass; exact upstream SOUL coverage is skipped on
Mac and mandatory/passed under the installed native interpreter.

For #761, retain immutable route confinement, private receipt verification and
integration-specific pass/fail/skipped semantics; repeat activation must preserve
imported payloads, and source/build success alone is not installed acceptance.
For #762, use a **fresh non-authoritative export** if access/state is stale and
revalidate. A retained original bundle can test exact reimport without contacting
NAS. Never replay quarantine or rotate copied Codex refresh tokens. A failed or
expired authenticated check is a gate, not permission to broaden credentials.
Keep production vault writer coordination, all-peer exclusion, restore authority
and final coherent transfer/cutover as separate #762/#763 gates.

Runtime rollback after importing auth must use a **receipt-aware compatible
staging generation**; pre-#760 reconciliation rejects imported credentials and is
not an automatic rollback target. Keep current/import preimages and private
transaction receipts; an incomplete transaction requires exact recovery review,
not cleanup or auto-restore. No source/service mutation, ownership-doc switch,
production pause/restore or destructive cleanup is authorized by this procedure.

## Explicit cross-project operations handoff (#761)

pi-cielo owns `mise run hermes <nas|omarchy> <command>` and its workstation human
proposal reviewer. system-config alone owns native installation, managed assets,
provenance/reconciliation, service and host-local operators. The existing vault
still owns task/atomic helper source; six approved private skills/nine files remain
user-owned, individually gated outside Git/Nix and active discovery. NAS remains
production. The canonical cross-project runbook is pi-cielo's
`docs/hermes-native-operations.md`; proposal review is in
`docs/hermes-promotion-handoff.md`. Run those tasks from pi-cielo, not system-config.

#761 tested the actual new interface on
`/nix/store/1niz7n62p49clj7gwvlvvsyc85rskzzj-home-manager-generation`:
metadata/unit/entrypoint/receipt/refusal gates, disposable tmpfs doctor,
no-refresh supported integrations, 16 disposable actual task/private-skill cases,
fixed capability/vault safety, inactive brief and secret-free log summaries passed.
Receipt-owned bytes/mtimes/modes and NAS inspect continuity were preserved. No new
native source/package/service changes or activation were needed for #761; this is
a documentation-only handoff, not production ownership or authority transfer.

For #762, use current installed metadata and the fixed launcher; the pi-cielo
wrapper's `runtime`, `state`, `doctor`, `credentials`, `parity`, `vault`,
`vault-safety`, `commands`, `cron` and `status` operations return semantic checks.
`reliability`/`handoff` are isolated capability-check aliases, not production
Telegram/proposal publication. Doctor exit0 is not green health. Never refresh a
copied rotating Codex grant, including expiry; keep real staged payloads sealed.

After imported credentials, #760's tested receipt-aware compatible generation is
`/nix/store/v2nyqwqag3rkyyzfqqlzyjhxf15r6g8g-home-manager-generation`; accepted return
candidate is `1niz7n62p49clj7gwvlvvsyc85rskzzj`. Before separately authorized rehearsal,
verify candidate metadata/operator/reconciler, schema/baseline paths, private
receipt/original snapshot and disabled gateway/production writes, capture current
profile/source/unrelated state and check stability. Do not run the older generic
foundation rollback snippets above. Activation restores runtime only, not data;
production rollback still needs exact restore authority, all-writer exclusion,
post-cutover state reconciliation and fresh coherent checkpoints.

Production controls (`start`, `stop`, `rollback`, `host-switch`) in pi-cielo always
refuse before SSH; proposed commands and ordered #763 host switch are documented,
not executed. No NAS modification, polling/send/brief/vault enablement, production
namespace switch, reboots/linger/logout/suspend changes or ownership-doc switch
was performed. #762 can rehearse isolated gates only; #763 requires John's distinct
final cutover decision. #756 remains incomplete. No commits/pushes/card closure.

## Isolated rehearsal and current installed acceptance (#762)

[#762](https://app.fizzy.do/6284043/cards/762) is the last **preparation** card,
not #763 final cutover. Current accepted generation on 2026-10-10 New York /
2026-10-11 UTC is
`/nix/store/wk04wzag7dcl79ki1203q5mhm7w03hgv-home-manager-generation`.
It supersedes #761's `1niz...` for current validation/return activation. Version,
source revision, four baseline roots and disabled/non-authoritative gates are
unchanged. The detailed evidence matrix, John checklist, provisional downtime
budget and ordered **future-only** cutover/rollback runbook are in pi-cielo's
`docs/hermes-native-operations.md` (#762 section), not executable controls here.

A real parity regression was exposed after UTC midnight: without host zoneinfo
inside the sealed namespace, libc/GNU `date` fell back to UTC despite
`TZ=America/New_York`, while Python's packaged zoneinfo used the correct New York
day. Weight/daily-task/brief cases initially failed (13/16). The actual Nix unit/
launcher now supplies pinned `TZDIR=${runtimePkgs.tzdata}/share/zoneinfo`, retained
in the minimal direct-plugin child environment. Four fixed winter/summer/both-DST
boundary tests and actual task-date agreement run inside confinement. Exactly
five reviewed native source/test files were transferred after current stable CAS
preflight; build used the remote independent lock without updating inputs.
Actual candidate home-files differed only in Hermes entries. Dry-run/activation,
full installed foundation/capability/vault-safety checks and **16/16 actual
parity cases** passed; this is Omarchy-only, with no Mac activation needed.

Fresh restricted NAS export streamed directly to **disposable** Omarchy data:
seven SQLite online backups with live WAL and integrity/foreign-key/FTS/schema30/
relationships, 24 receipt-owned payload paths, 32 quarantines and five claim tables
cleared only on copies. First import/path rewriting, repeat changedFiles=0,
independent seven-DB restore, private permissions and drift/incomplete-journal
refusal passed. Existing actual staged payload/auth and original receipts stayed
exact. Fresh vault snapshot/disposable restore/full metadata/xattrs passed; no
production pause/canary/restore or global coherence is inferred. All three real
Syncthing peers were idle/100% with zero needs/errors by read-only GETs; topology
and actual services were unchanged.

Receipt-compatible `v2ny...` rollback and return to `wk04...` passed actual
unit-environment version/state checks. Imported bytes/ns-mtimes/modes/UID/GID,
original backup/receipt, unrelated profile/bin contents and final symlink targets,
Syncthing/Herdr PIDs, remote independent lock and existing Linger=yes were preserved.
`v2ny...` lacks the corrected timezone: it is a **staging runtime** compatibility
proof, not a full-capability production scheduler fallback. Synthetic reverse
reconciliation preserved both incident branches, stopped on colliding IDs/stale
note preimages, and preserved an explicitly reviewed union/idempotency history
with pending work quarantined. The actual vault atomic helper passed CAS/refusal/
retry; a general production reverse importer/authority is not established.

Measured bundle57,436,160 bytes; receive7.088s includes export wait,
validation+import1.220s, repeat1.515s, restore0.611s, full combined invocation12.796s.
Rollback/return1.585/1.526s; fresh vault snapshot+disposable restore0.449s.
**NAS never stopped; production downtime was not measured.** Future approved
maintenance budget is provisionally1–5 minutes plus an agreed observation window,
not an SLA or a measured final coherent transfer.

Final credentials: read-only Codex usage, both Calendar accounts on tmpfs copies,
passive NotebookLM CSRF/session fetch PASS; no inference/refresh/private uploads.
Doctor has exactly two expected advisories, not green production health. Copied
Codex grants may expire: stop on EXPIRED_NO_REFRESH_FRESH_EXPORT_REQUIRED, never
rotate while NAS owns the grant; only scoped fresh export/revalidation is allowed.
Messages remains UNSUPPORTED_SCHEMA. Six private skills remain user-owned/outside
host discovery with individual enabling gates. One 05:00 New York no-agent brief
is INACTIVE, no timer/delivery; native gateway remains inactive/unstartable and
productionWrites=DISABLED.

**Preparation acceptance PASS/GO; production cutover NO-GO pending owner decisions
and #763 gates.** Writer coordinator/shared lock/all-peer exclusion, restore
authority/pause order, actual peer binary interoperability, globally coherent final
transfer/queue decisions, credential ownership and production Telegram/brief/write/
availability acceptance are not approved by this rehearsal. Existing Linger=yes,
linked/no-WantedBy/Restart=no staging unit and currently absent running hypridle
were observed; reboot/logout/suspend and 24×7 availability were not tested. No
sleep/desktop/linger policy changed. No NAS modification, ownership-doc switch,
final transfer, commits/pushes or card closure. #756 remains incomplete.
Private evidence stays under `/home/johna/.cache/hermes-native/rehearsal-762-clQN01TW`.

## Accepted production task access (#774)

John accepted the native migration. Its temporary terminal allowlist and read-only
vault mount are not the intended ongoing command policy. The accepted gateway
uses the original Hermes terminal handler for ordinary commands, including its
existing dangerous-command approval handling. Task discovery (`mise tasks ls`),
`mise run get-weather`, the inline `weight` and `nlm` tasks, and `recipe-tables`
are accessible again. There is no new per-feature approval or task-code hash gate
on ordinary task access. The existing literal native vault/writer adapters and
repaired Calendar routes remain available; failed/uncertain native operations
never fall through to a second execution.

The gateway's mounted Personal vault is writable for the original task helpers,
which retain their own flock/atomic writes and existing conversational rules.
The sealed namespace still excludes John's host agent profiles, SSH, and host
credentials, and keeps the ownership controller read-only. Exclusive native
ownership, poller/scheduler controls, no implicit login/recovery, privacy rules,
and one-production-copy safeguards remain unchanged. `HERMES_NATIVE_TASK_ACCESS`
marks accepted original task access; `HERMES_NATIVE_READONLY` remains the legacy
read-only **plugin/adapter** marker, not a terminal task allowlist.

Use `tests/hermes-native-command-access.py` for routing/approval/no-retry tests.
On Omarchy, `HERMES774_METADATA` explicitly enables an isolated real-task fixture
using installed tools, copies of task code, synthetic notes, no credentials, and
a deterministic weather provider. It checks discovery, a real weight write,
NotebookLM CLI help, and bulk recipe dry-run without touching production notes or
calling legacy Pi wrappers. This is focused evidence, not a claim that every
underlying task or live NotebookLM/video operation has been tested.

Only Omarchy imports this module. Preserve its unrelated source-snapshot edits
when transferring patches. A Home Manager build/activation is not proof that an
already running gateway has adopted new code: verify the installed metadata and
the running process separately, and report any pending controlled restart.

### #774 deployment status

Deployed on **2026-10-12** after John's explicit deployment authorization. Current
generation: `/nix/store/22j7j05ahc8kbscig3czy5smwlxjd76r-home-manager-generation`.
The running gateway has original task access and a writable Personal vault, while
its ownership controller remains read-only. Both production skill copies match
the reviewed managed assets. Actual production-namespace task discovery and
NotebookLM help pass; ordinary write coverage remains confined to disposable
fixtures. Four regression suites ran 85 tests with one explicit optional skip.

The controlled same-owner restart preserved historical arming/acceptance,
credentials, the sole enabled no-agent brief, and the inactive staging namespace;
no NAS resume, state reimport, note restore, or acceptance replay occurred. NAS
was independently verified stopped/PID0/restart-disabled before and after the
restart. Deployment records retain the investigated systemd/monitor verification
corrections; no new sessions, messages, or uncertain writes occurred during those
contained startup attempts.

The current ownership receipt points to the private `currentNativeTaskAccessReview`
and startup-continuation evidence under `controller/task-access-deployments/`.
Retain that evidence and existing recovery assets for at least 14 days. This is
not new automatic resumption authority or a claim that every underlying task/live
provider flow has been tested. The separate frontmatter-tag recipe discovery is
tracked in [#776](https://app.fizzy.do/6284043/cards/776), not silently treated as
fixed by removing command restrictions.
