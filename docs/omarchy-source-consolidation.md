# Omarchy Git source consolidation

Tracked in [#781](https://app.fizzy.do/6284043/cards/781). The retired
`system-config-poc` and `system-config-amfaro` directories are not deployment
sources and must not be recreated, including as compatibility symlinks.
Their verified recovery copies remain under
`~/.local/state/system-config-retired/`; historical documentation mentioning
them records past deployments, not current activation instructions.

## One reconciled source

The reviewable source is `feature/consolidate-omarchy-config`, in the linked
worktree `.worktrees/consolidate-omarchy-config` below each host's normal
`~/dev/src/system-config` repository. The task worktree is provisional until
John authorizes committing/integrating it; the dirty Omarchy primary checkout
is not an activation target. Its independent changes must remain untouched.

Reconciliation keeps current local `main` as the baseline, including its newer
Pi wrapper formatting, worktree policy, rebuild routing, and stronger tests.
It recovers the deployed Hermes lifecycle guard/adoption tooling and fixtures,
and the personal-Claude Codex routing implementation/tests/documentation.
The three historical Python cache files are exact approved Hermes assets,
explicitly retained by `.gitignore`; other Python caches remain ignored.
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

Build with `--no-write-lock-file --no-update-lock-file`, compare actual Hermes
metadata and unit bytes against installed state, and run the lifecycle guard
before activation. Follow [the normal deployment procedure](omarchy-agents.md#apply).

## Source-path and live-runtime boundary

The deployed #781 repair removes all three source-CAS references to the retired
path. The installed runtime takes an explicit verified Git source location,
retains exact asset/lock/task comparisons, and binds that location into newly
produced engineering evidence. It rejects unrelated or unregistered repositories,
aliases (including copied Git pointers), source drift, and receipts lacking that
binding. Original acceptance/arming receipts are historical evidence, not files
to rewrite for a move.

The `engineering-ready` input must include `sourceRoot`, an absolute canonical
path to the ordinary checkout or a registered task worktree. Fresh
`engineering.json` includes that location beside `sourceHashes`; subsequent
engineering/final-gate checks revalidate it and the exact source/lock bytes.
No legacy receipt is migrated implicitly. Run
`mise exec -- python3 -I -B tests/hermes-engineering-source.py` for eleven
synthetic, read-only source/receipt regressions; they do not qualify a live owner.

Changing runtime bytes changes its approved identity. A successful source
build or synthetic test does not grant a live code transition or restart.
The candidate was refused while the old owner was live, then deployed only after
John authorized finishing the proposed native-only update. The one-time
`hermes-source-path-transition.py` route pins both reviewed runtime hashes,
preserves the cold native state and historical receipts, and resumes the same
owner once. It consumes fresh actual NAS observations from a trusted parent
operator over stdio, without copying credentials or inventing a human/distributed
writer freeze. The retained qualification validates the previous complete
approval chain as well as the exact new immutable generation. It never grants
future automatic resumption or approval for a different candidate.

The update ran from the isolated `feature/hermes-source-path-transition` worktree
so independent #783 policy edits in the reconciliation worktree were not applied
or overwritten. Both task worktrees contain the exact repaired Hermes assets;
the reconciliation source retains those independent staged policy edits.
No automatic retry, rearm, acceptance replay, or native/NAS fallback is permitted.
