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

## Host-only locked revisions

Omarchy's deployed snapshot had three older revisions than local `main`.
Neither wholesale lockfile replacement nor an incidental package upgrade is
appropriate for source cleanup. Existing shared lock nodes stay unchanged;
only Omarchy's Home Manager output uses these additional, exact inputs:

| Input | Deployed revision |
| --- | --- |
| `omarchyNixpkgs` | `151fa4e8ddfdd8dd25d945ad94ed54a13de9f6e4` |
| `omarchyHomeManager` | `fae6e9e42c3b762ab47635cddcfaf6f52374a61b` |
| `omarchyHerdrProjectPicker` | `70219b8e1157f85dab8a8b9cf3b67907e6ca969d` |

The Omarchy Home Manager input follows `omarchyNixpkgs`. Mac and other hosts
continue using their existing shared inputs. These pins preserve deployed
package/unit identities without downgrading other hosts; upgrading them is a
separate reviewed deployment, not part of directory cleanup.

Build without updating inputs and follow [the normal deployment
procedure](omarchy-agents.md#apply). Hermes does not gate Home Manager activation.
