# Omarchy Git source consolidation

Tracked in [#781](https://app.fizzy.do/6284043/cards/781). The retired
`system-config-poc` and `system-config-amfaro` directories are not deployment
sources and must not be recreated, including as compatibility symlinks.
Their verified recovery copies remain under
`~/.local/state/system-config-retired/`; historical documentation mentioning
them records past deployments, not current activation instructions.

## One reconciled source

The original recovery and later deployments copied newer source into linked
worktrees without advancing Omarchy's old Git branches. Cleanup under #792/#781
reconciles those overlays against the recorded Mac history, preserves the two
remote-only documentation/test corrections, and fast-forwards Omarchy's local
`main`. Complete, verified source archives and the original Git bundle are retained
under `~/.local/state/system-config-recovery/20261016-wrap-cleanup/`; these are
recovery copies, never deployment inputs. No credentials or sessions are included.

Use the synchronized `~/dev/src/system-config` repository as the primary checkout.
Create each deployment's task worktree from its local `main`, transfer reviewed
commits/files, then integrate completed work and retire that task worktree. Do not
reuse a historical deployment worktree or copy a newer tree over stale recorded
history. Inspect and preserve any independent changes before synchronization.

Reconciliation keeps current local `main` as the baseline, including its newer
Pi wrapper formatting, worktree policy, rebuild routing, and stronger tests.
Hermes now uses the upstream gateway and ordinary systemd management. The
migration controller, bespoke lifecycle guards, fixture suites, and historical
bytecode exceptions were removed in #787. The recovered subscription-proxy and
agent configuration remains independent of that removal.
No credentials, mutable profile state, or sessions are source inputs.

## Shared inputs

Omarchy, Miller, Drummer and the homelab hosts use the shared `nixpkgs` and
`home-manager` inputs, so `mise update-system` moves them with the Mac. The
#781 host-only pins (`omarchyNixpkgs`, `omarchyHomeManager`) were retired in
#1392 after they left Linux packages months behind.

Build without updating inputs and follow [the normal deployment
procedure](omarchy-agents.md#apply). Hermes does not gate Home Manager activation.
