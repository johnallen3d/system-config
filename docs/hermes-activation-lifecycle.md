# Native Hermes and Home Manager activation

Tracked in [#771](https://app.fizzy.do/6284043/cards/771). Production cutover
[#763](https://app.fizzy.do/6284043/cards/763) remains separate and open.
This module is Omarchy-only; Omarchy uses standalone Home Manager, not NixOS.

## Current Git-based source and #780 repair

On 2026-10-12, [#781](https://app.fizzy.do/6284043/cards/781) retired both historical
standalone source directories into verified recovery archives. Current deployment
source is `~/dev/src/system-config/.worktrees/consolidate-omarchy-config` on
`feature/consolidate-omarchy-config`; the primary checkout's unrelated edits remain
untouched. Exact approved asset bytes, including three historical Python cache
artifacts, are preserved explicitly rather than exempted from identity checks.

The #780 read-only guard repair was activated from that Git worktree. It recognizes
the exact retained current calendar/task approval chain described below. The
pending #779 personal Pi/Claude instructions and prompts were activated and
verified, with Hermes PID/invocation and protected receipts, credentials, jobs and
ownership unchanged. No scheduler delivery or Telegram readiness claim follows
from this source/activation verification.

The #781 source-path repair is now **deployed**. It replaces all three retired
directory references with an explicit `sourceRoot`, validated against the
ordinary Git repository and its registered worktrees. New engineering evidence binds this
location while retaining every exact asset, independent-lock and task-code CAS.
The one-time adoption tool activates an absolute generation from `/`, not a
retired checkout. Eleven synthetic source/receipt regressions cover relocation,
drift, missing binding, aliases, copied Git pointers and foreign repositories.

John authorized finishing the update after the explicit native-only
stop/update/resume proposal. The controlled update preserved a cold seven-database
checkpoint and the original arming/acceptance receipts, jobs and secrets. It
verified the actually stopped/protected NAS through the parent operator's existing
trusted SSH connection; no keys were copied and no NAS action was performed.
Hermes paused for approximately 18 seconds, then its new Telegram polling
connection was observed. No acceptance or delivery was replayed.

The owner hashes a separate one-off source-path qualification. The read-only
guard validates its exact runtime pre/postimages, retained authorization,
immutable old/new generations, and complete earlier calendar/task approval chain.
Invalid newer evidence never falls back to old approvals; another code change
still fails before activation. This does not grant future automatic resumption,
a distributed/human writer freeze, continuous availability or scheduled delivery.
Do not recreate an alias, bypass checks, rearm, replay acceptance or activate an archive.

The #771 chronology below records historical snapshot paths, not current targets.

## Incident and mechanism

On 2026-10-11 (UTC), initial native ownership reached `NATIVE_LIVE` at
13:22:55.731199. The real standalone activation log at
`/tmp/personal-worktree-deploy.RcBMlu/activation.log` records `linkGeneration`,
then `reloadSystemd`, then `Stopping units: hermes-production.service`.
The user journal records the stop at 17:11:50, supervisor exit status 64,
and failed/stopped unit. The supervisor deliberately revokes native poller,
scheduler, provider-refresh and vault-write authority in its exit path.
The unit has `Restart=no` and no boot/login enablement: it does not automatically
restart, and an ordinary start is not permission to bypass ownership/arming.

Although the asset/fixture bytes were identical, metadata used paths such as
`/nix/store/<whole-flake-hash>-source/modules/home-manager/hermes-native` and
`/nix/store/<whole-flake-hash>-source/tests/...`. `toString` of an evaluated flake
subpath retained the containing source path. Unrelated repository changes
therefore changed exact metadata, launcher and systemd unit references.
Home Manager's `sd-switch` reconciled the changed foreground unit; the original
arming identity no longer matched. This was not an authentication rollback or
a reason to restore old databases, jobs or credentials.

The authorized same-owner recovery at 19:19:39 preserved the original arming
and acceptance receipts and recorded a separate hashed qualification receipt.
The journal shows an actual Telegram polling-mode connection at 19:19:41.803.
The current owner references that qualification under
`controller/engineering-runs/authorized-same-owner-resumption-*/qualification.json`.
Its `currentCode` is the recovered binding; `arming.json.code` deliberately
remains the original accepted binding. Future automatic resumption is **false**.

These observations do not establish the first failed Telegram request,
continuous availability, or a delivered scheduled brief. An active PID,
fixture success, configured job, or historical polling connection alone does
not establish those outcomes.

## Prevention

`omarchy-hermes.nix` content-addresses a fileset containing the entire
`hermes-native` asset subtree and the three production fixtures. It preserves
`modules/home-manager/hermes-native` and sibling `tests` layout: the actual
installed fixture runner imports those paths and requires equivalent bytes.
No store-hash normalization or asset hash exemptions are introduced.

Unrelated flake changes and byte-equivalent restores retain **exact** production
metadata and `ExecStart`. An asset, fixture, package, environment or effective
unit change still changes the relevant approval identity.

`hermesNativeLifecycleCheck` runs before Home Manager's `writeBoundary`,
`linkGeneration` and `reloadSystemd`. It is read-only and fails activation if:

- A native running owner and service disagree, or the installed receipt binding
  is invalid. Missing/unknown owners, transitioning units and unexpected
  effective overrides fail closed.
- A live candidate changes exact metadata or installed unit bytes.
- A revoked or NAS/CLOSED owner still has a native process or capability enabled.

It recognizes the **existing**, owner-hashed one-off resumption only when its
original and current code identities, archived immutable metadata and recorded
authorization match exactly. It also recognizes the separately approved #771
packaging-adoption receipt: only the exact reviewed old/new
`production-module.nix` hashes and metadata may differ from original arming;
all other asset hashes remain identical. Both receipt forms bind the exact
current metadata to an archived immutable generation and forbid future automatic
resumption. The preflight creates no receipt, rebinds no owner, normalizes no
candidate and starts no poller. Another generation with identical metadata is
not itself a code change.

[#780](https://app.fizzy.do/6284043/cards/780) also recognizes the existing later
#774 task-access deployment, ahead of stale packaging evidence. This is a narrow
read-only binding: the arming-hashed #763 calendar review must match current arming,
the same source bundle, its immutable historical generation and all seven retained
acceptance receipts. The owner-hashed #774 qualification must carry its exact
reviewed authorization, preserve historical arming/acceptance, forbid future
automatic resumption, and match the complete installed code identity and immutable
generation metadata. Invalid newer evidence fails closed; it never falls back to
an older approval. New candidate metadata, units or asset bytes still require the
controlled lifecycle. No receipt, credential or live process is rewritten.

A fully revoked, inactive owner may install a candidate. This returns
`STOPPED_INSTALL_ONLY`, not start/arming permission. Existing approval,
engineering, source-exclusivity, writer-freeze, acceptance and no-replay gates
remain authoritative. Do not disable this module, uninstall Home Manager,
rollback to a pre-cutover generation, bypass the check, or race activation
against another lifecycle operation. This preflight is a bounded check, not a
new distributed lock or a replacement for the controlled lifecycle.

Other Home Manager pre-boundary migrations can precede the check. The guarantee
is refusal before generation/package/systemd writes, not that every unrelated
migration hook has been prevented from running.

## Reporting scheduler authority

Run `hermes-native-lifecycle` for read-only status. The passive operational guide
is installed at `~/.config/hermes-native/activation-lifecycle.md`, deliberately
outside the runtime approval identity. For source-based checks:

```bash
mise -C ~/dev/src/amfaro exec -- python3 -I -B \
  /absolute/task-source/modules/home-manager/hermes-activation-check.py \
  --home /home/johna --status
```

`configuredEnabled` describes preserved `cron/jobs.json`; `executionAuthorized`
additionally requires the live native owner and scheduler capability, active
service and valid binding. A revoked/stopped owner reports no execution
authority even if the job is configured enabled. Neither field is a delivery
receipt. `telegramReadiness=NOT_PROBED` and `scheduledDelivery=NOT_VERIFIED` are
intentional. Owner/service disagreement is an error, never an optimistic
"enabled" report. This helper does not rewrite jobs or change upstream Hermes's
configuration-only job display.

## First adoption and genuine changes

The first transition from the whole-flake source to the bounded fileset changes
an approved path/code identity. The live preflight must reject it. Do **not**
treat the successful build or byte-equivalence comparison as permission to
modify the original arming/acceptance receipts or repeat the one-off CAS recovery.

1. Agree an explicit controlled execution window and the existing required
   approvals, receipts and writer freeze. Inventory source exclusivity and all
   active/uncertain work; retain latest auth, seven databases, jobs and original
   receipts. Do not reset/replay work or resurrect NAS/staging sources.
2. Use the production controller's authorized containment procedure, which
   revokes authority before stopping the native supervisor. Verify the owner
   and actual unit are fully stopped. Do not use a broad configuration rollback.
3. Inspect divergence in the verified Git task worktree under
   `~/dev/src/system-config/.worktrees/`;
   transfer only intended changes. Build its standalone activation package
   without updating inputs and activate only within the approved lifecycle.
4. Complete the required reviewed-code/receipt transition through that
   lifecycle. The preflight is not an approval or restart command. The reviewed
   `hermes-packaging-adopt.py` is a **one-time** explicit #771 adoption route,
   not a general change/restart command: fixed module preimages, identical
   controller/fixture bytes, exact translated launcher/unit bytes, fresh John
   window and actual NAS/peer observations are required. It checks no active or
   uncertain work, retains a cold seven-database/auth/job/receipt checkpoint,
   uses the existing revoke-before-stop operation and preserves original arming.
   It installs while stopped and authorizes only this exact reviewed native
   owner through a separately hashed receipt. Failure after containment leaves
   ownership revoked for review; there is no retry, rollback or NAS action.
   `--qualify` is read-only; `--adopt` requires an explicit private request from
   an actual approved window. It never generates human approval. Do not rerun
   completed adoption, acceptance tests or deliveries.
5. Verify exactly one actual Telegram poller, exclusivity, readiness and current
   effective installed identity. Then exercise an unrelated real activation,
   retaining that readiness. Verify a **distinct scheduled** morning brief
   end to end, with its delivery receipt and no duplicate/uncertain replay.

## Validation and current deployment status

- `tests/hermes-activation-lifecycle.py`: 39 synthetic read-only identity, owner,
  effective-unit, receipt-tampering, narrow adoption, current-review binding and
  scheduler regressions. The historical #771 module postimage is a verified test
  fixture, not replaced with today's differently approved module.
- `tests/hermes-packaging-adopt.py`: 8 focused exact module/pointer/byte,
  semantic-change and missing-approval regressions. No live service or network.
- `tests/hermes-activation-nix.py --source /absolute/source`: actual standalone
  Home Manager evaluation on Omarchy. Checks real Nix-store fixture layout,
  exact stability under unrelated edits/byte-equivalent restores, and changed
  identities for asset/fixture mutations. Never activates or touches live state.
- The candidate activation package builds on Omarchy; installed-shape production
  suites run (9 state, 51 transfer with 18 skips, 14 writer tests). Skips are not
  acceptance evidence.
- A real candidate activation **dry-run** refused the live migration before
  `writeBoundary`. Owner/arming/acceptance receipts, jobs and the live PID were
  unchanged. The current-generation read-only check recognizes the existing
  recovery receipt and passes.

**Omarchy migration deployed under John's explicit approval on 2026-10-11.**
Intended files were transferred into the actual `system-config-amfaro` snapshot
with preimage checks, preserving its independent lock, existing bytecode and
unrelated source. The remote POC guide lacks local main's historical cutover
summary; only the nonconflicting lifecycle pointer was inserted there.

The controlled transition retained a cold checkpoint of all seven databases,
latest auth/jobs, all **68** then-delivered obligations and original receipts. Activation changed none of those bytes;
startup may legitimately refresh native auth, whose latest bytes are retained,
never replaced by a preimage. Initial adopted generation:
`/nix/store/aqchfhc9p11n1f30m6msjz5dx83k06gq-home-manager-generation`.
Its hashed approval and readiness records are under
`controller/engineering-runs/packaging-adoption-g7syq0on/`.

The new native invocation `a5e3e68d3eaa4ee0ac3e673eaa9e2286` reached an actual
Telegram polling-mode connection, verified at 2026-10-11 21:49:30 UTC, MainPID
42118, after approximately **16 seconds** of controlled maintenance. Original
arming/acceptance receipts and configured jobs were unchanged. One actual
native Python gateway child was observed; NAS remained protectively stopped,
staging inactive and all three peers clean. No completed acceptance or send was
repeated, no state restored/reimported and no uncertain work replayed.

A **real activation into a different generation** installed the passive guide:
`/nix/store/1asx06z4ianf4djl7gg049wfmkmpjmdk-home-manager-generation`.
The preflight passed, `reloadSystemd` ran, all existing service units and exact
Hermes metadata remained identical, and the same live PID/invocation continued.
Original receipts/jobs were unchanged; Hermes was not stopped or restarted.

A separate semantic candidate set `runtimeEngineeringReady=false`. Its actual
activation dry-run refused before `writeBoundary`, explicitly requiring a
controlled lifecycle. Live ownership, poller and protected receipts stayed
unchanged. This is failure-gate evidence, not permission to deploy that candidate.

A post-adoption audit verified all 68 original delivered obligation rows were
logically unchanged and **one new Telegram delivery** was acknowledged after
the successful unrelated activation (and after the new invocation's readiness
check). This supports actual post-update Telegram operation without replaying
completed acceptance. It does not establish
continuous availability or a scheduled-brief delivery.

A later, separate reviewed native-calendar deployment rebound active arming
and restarted the gateway at 22:13 UTC, after the #771 validation above. Its
`HERMES763_REVIEWED_CURRENT_NATIVE_CALENDAR_CODE_CONTINUATION` receipt is
owner-referenced and hashed. The original arming remains byte-identical in both
the #771 cold checkpoint and that deployment's `previous-arming.json`; original
acceptance/secret/job records remain unchanged. Current source, metadata and
unit match the installed Home Manager generation. Do not overwrite or roll back
that separately reviewed code/arming to make the earlier PID or hashes match.
The preservation and unchanged-poller evidence above describes the #771
transition/activation, not a claim that no subsequent authorized rollout occurred.

The distinct brief remains scheduled for
**2026-10-12 05:00 America/New_York (09:00 UTC)**; its end-to-end delivery and
qualified observation still remain pending. The maintenance interruption is
explicit: do not claim continuous availability or completed #763 observation.
Mac does not import this module and needs no activation. Keep #771 and #763
open; do not claim all acceptance criteria are complete.
