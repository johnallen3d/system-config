# Native Hermes on Omarchy

Hermes uses its upstream gateway, terminal tools, approvals, credential handling,
and scheduler. There is no bespoke Python supervisor, broker, migration controller,
writer gate, approval-receipt chain, or Hermes activation preflight.

Home Manager owns the pinned package, launchers, systemd user service, and the
existing `/search` and `/macros` integration plugins. Their task dependencies are
provided through a private Nix PATH. Ordinary argument validation and subprocess
timeouts in those integrations are not migration or runtime authorization gates.

## Normal operations

```bash
systemctl --user status hermes-gateway-0d366c1d.service
systemctl --user restart hermes-gateway-0d366c1d.service
journalctl --user -u hermes-gateway-0d366c1d.service -n 50
hermes-production gateway status
```

The service uses upstream Hermes's unit name for this production home:
`hermes-gateway-0d366c1d.service`. It starts with the user session and restarts
on failure. Upstream Hermes handles runtime execution and single-instance checks.
Use systemd for service lifecycle: upstream `gateway install`/`restart` tries to
rewrite the service file, which is read-only because Home Manager owns it.
`hermes-production` and
`hermes-native` both expose the upstream CLI with the production environment;
bare `hermes` and `~/.hermes` remain user-owned and are not changed.

## Existing state and integrations

- `HERMES_HOME`: `~/.local/state/hermes-native/production/baseline-0.21.2`.
- Isolated `HOME`: `~/.local/share/hermes-native/production/baseline-0.21.2/home`.
- Vault and terminal working directory: `~/notes`.
- Credentials stay on Omarchy, in Hermes's existing auth store and private `.env`;
  they are never copied to another host or written to the Nix store.
- Conversations, databases, jobs, memories, and private skills remain in place.
- The existing scheduled morning brief runs the vault's `mise run morning-brief`
  with `MORNING_BRIEF_DELIVERY=stdout`; upstream Hermes handles delivery.

Legacy controller receipts are retained only as inert historical state. They have
no authority over startup, restart, configuration activation, tools, or scheduling.
Do not restore an old migration-era generation as a routine recovery operation.

The NAS-to-Omarchy cutover is complete. Do not re-import NAS state or restart the
retired NAS instance when maintaining this native service.
