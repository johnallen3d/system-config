---
name: improvement-proposal
description: Describe a constrained native skill proposal for human-reviewed system-config promotion; publication is gated in staging.
---

# Hermes promotion handoff

## Native staging gate

Publication is unavailable in this staging runtime. `hermes-native-propose` is
not installed or exposed; do not invoke another interpreter/exporter or write
proposal files manually to bypass this gate. The fixed, isolated
`hermes-native capability-check` alone exercises `proposal-create.py` against
disposable fixtures. Real vault publication requires the #759 write gate and
later explicit activation.

Native managed assets belong only to `system-config`, below
`modules/home-manager/hermes-native/`. A native proposal declares schema 2 and
owner `system-config`; it must never target the NAS source in `pi-cielo`.
The human reviewer lives in `pi-cielo` and requires both `--target-owner
system-config` and an explicit `--repo` pointing to the reviewed checkout.
A proposal grants no commit, promotion or deployment authority.

Use this workflow when John asks to preserve, propose, or hand off a Hermes
runtime skill improvement. A proposal is not approval, promotion, deployment,
or permission to access workstation state.

## Boundaries

- Work only with runtime files below `$HERMES_HOME/skills/`.
- Never install or invoke Pi, copy `$PI_CODING_AGENT_DIR`, seek the `pi-cielo`
  checkout, or depend on a workstation path.
- Never place credentials, tokens, passwords, allowlists, private keys, account
  identifiers, or secret-bearing configuration in a proposal.
- Do not write proposal files directly into the vault. Use only
  `hermes-native-propose`, which constrains paths, scans artifacts, records
  hashes, and publishes the complete proposal atomically.
- Do not claim a proposal was reviewed, promoted, committed, or deployed.

## Procedure

1. Identify each changed file below `$HERMES_HOME/skills/` and confirm it differs
   from the Nix-owned baseline below `$HERMES_NATIVE_ASSETS/skills/` when one exists.
2. Inspect the complete proposed files for private or environment-specific data.
3. Write a concise rationale to a temporary file outside the vault, such as
   `/tmp/handoff-rationale.md`. Include behavior, safety impact, and why the
   change should become system-config-managed.
4. Choose a stable lowercase ID such as `20260916-clearer-macros-help`.
5. Name concrete validation commands or manual checks. Proposed test text is
   review material only; neither exporter nor reviewer executes proposal-supplied scripts.
6. Run the deterministic exporter, repeating `--file` and `--test` as needed:

   ```bash
   hermes-native-propose \
     --id 20260916-clearer-macros-help \
     --title "Clarify the read-only macros command help" \
     --rationale-file /tmp/handoff-rationale.md \
     --file skills/health/macros/SKILL.md \
     --test "mise run hermes commands"
   ```

7. Report the proposal ID and `proposed` status. Explain that Syncthing and the
   Personal vault Git backup must capture it before a human can review and
   promote it on the workstation.

If the exporter reports an unchanged baseline, secret match, invalid path, or
existing proposal ID, stop and resolve that error. Never bypass the exporter.
