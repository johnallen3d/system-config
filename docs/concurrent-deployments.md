# Concurrent deployments

[Fizzy #824](https://app.fizzy.do/6284043/cards/824).

Concurrent tasks are normal; deployment preservation is not Git integration.
Only the invoking task's authorized changes and **verified already-active** task
layers enter a deployment. Other dirty worktrees and pending implementations are
never automatically collected. For example, preserving active PaddleOCR/Pocket
#819 does not authorize activating the pending Credits replacement #823.

## Entry points and discovery

The Nix-managed `system-config-deploy` command packages the current coordinator,
Mac tasks, and Omarchy worker independently of the task checkout. Use it even
from older worktrees whose own scripts predate coordination:

```bash
mise exec -- system-config-deploy "$task_path" --switch-only
```

On Mac this applies both hosts in parallel; `--local-only` explicitly excludes
Omarchy. Existing input-update and harness flags retain their meanings. On
Omarchy use work context and an absolute source path:

```bash
mise -C ~/dev/src/amfaro exec -- system-config-deploy "$task_path" --switch-only
```

Linux activation is host-local and requires `--switch-only`; it never runs a
macOS rebuild. Source/history synchronization remains a separate guarded step
for Linux-only recovery. Do not use a raw Home Manager activation to bypass the
coordinator. Current repository `mise update-system` and `mise run nix-rebuild`
also coordinate; older task copies must use the installed command instead.

Inspect each target host **before planning activation**:

```bash
coordinator="$HOME/.local/share/system-config-deploy/.mise/scripts/deployment_state.py"
mise exec -- python3 "$coordinator" status "$task_path"
```

Status reports the actual kernel-lock state, last lock holder metadata, active
and pending receipts, and the installed generation. Stale lock metadata is not
an active lock. Receipts live at `~/.local/state/system-config/deployment`, outside
Pi/Claude profiles. They contain Git identifiers, task branch owners, origin
paths, generation paths, and source paths, never credentials or session data.

Each host has one advisory kernel lock covering source planning, build,
activation, verification, and receipt recording. A second task waits up to ten
minutes, then reports the owner and a retry action; it does not ask John whether
to discard work. After waiting it re-reads the active generation and layers.
Normal process exit releases the lock; do not delete lock files or kill another
agent. The Mac lock remains held until both host outcomes have been collected.
An interrupt waits for existing children rather than abandoning their lock;
no subsequent activation is started by a cancelled remote coordinator.
These are cooperative deployment tools, not a security boundary against raw
out-of-band commands or a privileged process killing a deployment's process tree.

## Source and ownership model

- Task identity is its branch name within this repository. Receipts also retain
  its origin checkout and captured HEAD. Verify task ownership before invoking
  deployment; do not impersonate another task by renaming a branch.
- A private Git index captures tracked changes and nonignored new files without
  altering task/main indexes. Ignored files and host profiles are excluded.
- Each layer records a base and a source tree. Planning starts from integrated
  local `main`, carries forward recorded active layers, and replaces only the
  invoking branch owner's previous layer. It does not read later edits to an
  already-deployed task's working copy.
- Composition is deliberately conservative **per file**, including file modes,
  symlinks, binary content, additions, and deletions. Identical edits coexist;
  different changes to the same path stop with both owners. This includes
  `flake.lock`. Even disjoint text hunks in one file require owner coordination;
  there is no speculative auto-merge.
- Main changes already identical to an active layer are absorbed and retired
  from that layer (including individual files in a multi-file layer). Later
  integrated edits are not mistaken for an unfinished task. Other overlaps with
  newer main stop; unrelated main changes are retained without rebasing a task.
- Composite source lives in `.worktrees/deployment-<source-id>` on its own
  `feature/deployment-<source-id>` branch created from main. It is reused only
  when ownership, base, and source match. No existing worktree is reset/deleted.
  Git tree refs under `refs/system-config/trees/` retain blobs through GC without
  creating commits or moving task/main branches.
- Mac and Omarchy compose against their own active receipts. Host-specific active
  overlays need not be imported into the other host's task source. Omarchy still
  synchronizes only clean, fast-forwardable integrated main history and receives
  only intended source, not profiles or credentials.

An active receipt binds the exact generation to reproducible composite source.
A pending receipt is written before activation. Success records it as active;
if the caller dies after successful activation, the next invocation recovers
only an exact installed-generation match with validated source. A failed build
keeps the previous active receipt; its unactivated layer is not carried forward.
Source tampering, missing Git objects, generation drift, or an out-of-band
rollback stop before another activation. Keep artifacts for investigation.
One host failing remains a **partial deployment**, even if the other succeeds.
Installed configuration and effective runtime verification remain required; a
receipt/build alone does not prove application behavior or authorize a restart.

## First adoption / recovery

Before the first coordinated activation, an agent must identify the source of
the installed generation using the active-generation path, existing task/card
ownership evidence, registered Git worktrees, and a no-update Nix evaluation.
Do not infer deployment from timestamps or build success. Do not scan dirty
worktrees and adopt all their changes just because some are irrelevant on this
host and therefore do not affect its output.

Once ownership is verified, bootstrap with:

```bash
mise exec -- python3 "$coordinator" adopt "$repo_root" "$verified_source" "$task_branch"
```

Adoption creates a source-frozen linked worktree and accepts it only when its
**evaluated output path exactly equals the installed generation**. It performs
no activation and cannot replace existing active or pending records. A verified
clean primary `main` may be adopted with owner `main`. Ignored files in the
primary checkout do not enter its source snapshot. If the active state includes
multiple tasks, establish their exact ownership/source layers rather than
misattributing them to a convenient branch. Ask John only when evidence cannot
establish ownership or a genuine conflict/new authorization decision remains.

For an unrecorded rollback or corrupted existing record, retain receipts and
worktrees and investigate the precise mismatch before proposing recovery; there
is no force/adopt-over-existing or reset-to-main switch. Do not edit a receipt
merely to make a candidate pass. A successful deployment does not authorize
commits, integration, pushes, worktree removal, service/agent restarts, or card
closure.

## Offline verification

```bash
mise exec -- python3 tests/concurrent-deployments.py
mise exec -- python3 tests/update-system.py
mise exec -- python3 tests/nix-rebuild.py
```

These checks use disposable Git repositories/worktrees and command mocks, not
host activations or synthetic commits. They cover active-but-unintegrated layers,
real same-file conflicts, private-index preservation, ignored secrets, symlinks
and binary/deleted files, failed/interrupted activation recovery, generation
mismatch, layer retirement, and two competing processes sharing the kernel lock.
