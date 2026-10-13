# Native Hermes vault editing

Native Hermes on Omarchy supports ordinary Personal vault note editing, not just
food, activity, weight, and list tasks. This is implemented by the supervisor's
`vlt-adapter.py` and terminal broker in `production-runtime.py` ([#772](https://app.fizzy.do/6284043/cards/772)).
No `config.yaml` permission toggle or separate Hermes installation is needed.
Ask the existing Telegram bot to create or edit a note normally.

## Available commands

Use a single literal command with explicit content, including quoted multiline
Markdown; the adapter does not evaluate a shell:

```bash
vlt vault=Personal create name="Example" path="inbox/Example.md" content="# Example"
vlt vault=Personal write file="inbox/Example.md" content="# Updated example"
vlt vault=Personal append file="inbox/Example.md" content="Another paragraph"
vlt vault=Personal prepend file="inbox/Example.md" content="Introduction"
vlt vault=Personal patch file="inbox/Example.md" old="Another" new="A revised"
vlt vault=Personal property:set file="inbox/Example.md" name="status" value="active"
vlt vault=Personal property:remove file="inbox/Example.md" name="status"
vlt vault=Personal search query="example"
vlt vault=Personal uri file="inbox/Example.md"
```

Read, properties, backlinks, links, files, tags, tag, tasks, orphans, unresolved,
and templates are also available. Existing exact raw YAML/JSON reads used by
managed skills remain supported. Use relative paths when titles are ambiguous.
Root-level Markdown paths are normalized internally to avoid vlt 0.11's
bare-filename `.md.md` lookup bug. New note folders may be created.

## Write safety and boundaries

The installed pinned vlt binary runs without network or model credentials,
against read-only real notes and a private writable target overlay. The
supervisor commits only the selected Markdown note, using the existing shared
writer lock, retained preimage, compare-and-swap, atomic replacement/readback,
and actual local/direct Syncthing acknowledgment. Frontmatter behavior is
upstream vlt's behavior. Ordinary vlt validation failures with no real-vault
changes do not revoke the gateway or leave an incomplete writer reservation.

This is vault editing, not unrestricted shell access: other vaults, traversal,
hidden configuration/task-code paths, shell wrappers/pipes, and unrelated
commands remain unavailable. Move/delete and configuration-bookkeeping commands
are not implemented by this note-postimage adapter. A generated `obsidian://`
URI can be returned in the normal conversation; it does not publish private
notes to an external service. Never imply that a local lock is a distributed
cross-host lock; avoid editing the same note concurrently on another peer.

## Validation and deployment

Run `mise exec -- python3 tests/hermes-vault-editing.py`. Parsing tests run on
Mac; all sandbox tests run on Omarchy with
`HERMES_VLT_FIXTURE_METADATA=/home/johna/.config/hermes-native/production.json`
and the installed metadata's Python interpreter. The fixtures contain synthetic
notes only. Existing production transfer/writer regressions remain relevant.

This module is imported only by Omarchy, so no Mac activation is needed. Deploy
only intended source changes to Omarchy's verified Git task worktree after checking for
divergence, build without changing its lock, and qualify the actual built assets.
For a real code update, wait for active turns and uncertain deliveries to clear,
perform a scoped reviewed stop/activation/resumption, and retain code-review and
cold-state preservation evidence. Do not overwrite current credentials,
rewrite/replay original acceptance receipts, reimport state, restart NAS, or
assume unrelated Home Manager activation preserves availability (see #771).
The production unit is `hermes-production.service`; `hermes-native` and
`runtime.json` refer to inactive staging, not the live gateway.
