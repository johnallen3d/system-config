# Omarchy host monitoring

Tracked in [Fizzy #734](https://app.fizzy.do/6284043/cards/734).

`hosts/omarchy.nix` imports `modules/home-manager/omarchy-beszel.nix` only on
Omarchy. This is a standalone Home Manager **systemd user service on Arch**,
not a NixOS service or a Docker deployment. Existing user lingering starts it
without an interactive login. No macOS or native desktop configuration changes
are required.

## Connection and security

- The native `pkgs.beszel` agent connects outbound to
  `https://beszel.jallen7usa.com` using WebSockets. Existing split DNS resolves
  this endpoint to pi-01's LAN address, `192.168.5.11`.
- `DISABLE_SSH=true` prevents a listening agent port, including while the hub is
  unavailable. Omarchy's observed DHCP address (`192.168.4.26/22`) is not a
  reservation or a monitoring dependency. No firewall, subnet-route, Caddy, or
  DNS changes are needed.
- Explicitly empty `DOCKER_HOST` disables container discovery and socket access.
  CPU, memory, uptime, and root-filesystem metrics work without root privileges.
  SMART/root-only metrics are outside this service's scope.
- Pairing files live in `~/.config/beszel-agent/` (directory mode `0700`):
  `hub.pub` is the existing hub's public key, and `token` is this system's pairing
  token (files mode `0600`). They are writable host-local files, never Home
  Manager `text`/`source` values, repository files, or Nix-store inputs.
- The fingerprint lives in `~/.local/state/beszel-agent-data/` (mode `0700`).
  Preserve it across rebuilds/restarts; generating another fingerprint can break
  the existing hub pairing. The state directory deliberately has a different
  basename from the pairing directory: systemd otherwise creates a legacy
  compatibility symlink from state to configuration.
- The service has a restrictive umask, no new privileges, read-only home/system
  access, and a writable state directory. `/proc` and `/sys` remain visible for
  host metrics. Do not enable `ProtectProc` or `ProcSubset=pid` blindly.

## Pairing and activation

The existing Beszel user configured in Glance owns **one** `omarchy` system.
Glance's Lab template iterates that user's systems automatically: there is no
host list or template change in pi-cielo. The record's `host=omarchy` and
`port=45876` are fallback metadata; the agent uses outbound WebSockets and does
not listen there. Sleep/offline periods leave the record visible as unreachable;
it reconnects automatically when network connectivity returns.

For a new machine or deliberate re-pairing, an operator should inspect the
existing system before creating anything. Obtain the hub public key and the
system-specific token through Beszel's authenticated Add/Edit System workflow.
Provision them securely into the protected files above, without printing them,
putting them in shell history, copying another user's credentials, or using a
universal token unnecessarily. This setup's original pairing used the existing
dashboard user on pi-02; credentials stayed in process memory and were not
copied to Omarchy. Preserve existing files rather than overwriting them.

Before activation, check the actual Omarchy snapshot for divergence and transfer
only intended changes. Keep its existing lockfile and unrelated edits. Follow
[the Omarchy activation procedure](omarchy-agents.md#apply); never run macOS
rebuild tasks on this machine. The current source is
`/home/johna/dev/src/system-config-amfaro`.

The unit skips startup if pairing files are absent. Once provisioned:

```bash
systemctl --user start beszel-agent
systemctl --user is-enabled beszel-agent
systemctl --user is-active beszel-agent
```

No coding-agent or Herdr restart is required. Removing this module and activating
the previous configuration stops monitoring, but intentionally does not delete
machine-local pairing/state or the Beszel system record.

## Verification

From the checkout, with Nix available:

```bash
python3 tests/omarchy-beszel.py
```

On Omarchy after activation:

```bash
python3 /home/johna/dev/src/system-config-amfaro/tests/omarchy-beszel.py --installed
```

The test checks evaluated host-only ownership, file-based credentials, disabled
inbound/Docker access, protected runtime files/state, service enablement, and no
listening sockets. It never reads pairing contents or changes service state.
Also verify independently through the dashboard user's Beszel API that exactly
one `omarchy` system is up with recent `1m` stats, positive uptime, memory/root
capacity, and current CPU/memory/disk percentages. Verify Glance's rendered
`/api/pages/lab/content/`, not only the empty `/lab` page shell.

A controlled stop/start should show Beszel down and Glance unreachable, then
recover with the same fingerprint. Allow for the widget's one-minute cache.
This was verified during initial deployment; an actual workstation suspend was
not forced. The other hosts remained up throughout.
