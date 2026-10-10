# Syncthing on Omarchy

Syncthing is enabled only by `hosts/omarchy.nix` using Home Manager's
`services.syncthing`. It runs as Johna's systemd user service, starts with the user
manager, and restarts on failure. Omarchy already has user lingering enabled, so
the service can run without an interactive login. Nix owns the binary and service;
Syncthing owns its writable device identity, credentials, pairing, and folder
configuration. Activation does not replace devices or folders added through the UI.

Open <http://omarchy.taila14c2.ts.net:8384> from any permitted Tailscale device.
No SSH tunnel is needed. Syncthing itself listens only on `127.0.0.1:8384`;
Tailscale Serve publishes that backend only within the tailnet. The browser URL
uses HTTP, but transport between devices is encrypted by Tailscale. Tailnet HTTPS
Serve is not enabled, so this setup does not require changing that tailnet setting.

The persistent Serve mapping is owned by Omarchy's native Tailscale daemon:

```bash
tailscale serve --bg --http=8384 --yes http://127.0.0.1:8384
```

`--bg` persists the mapping across Tailscale/node restarts. Never use Funnel or
bind the Syncthing GUI to all interfaces. Home Manager allows the reverse proxy's
Host header with `settings.gui.insecureSkipHostcheck = true`; the backend remains
loopback-only, and remote access is controlled by Tailscale ACLs. Set a GUI password
through Syncthing if additional application-level authentication is needed.
Other Tailscale Serve ports are left untouched.

## Pairing and vault capture

Installation alone does **not** synchronize a vault. Pair Omarchy with an existing
Syncthing device and share the intended vault folder. Confirm the destination
path, wait for synchronization, and then configure Pi's
`PI_SESSION_CAPTURE_VAULT_PATH` to that local vault path. Do not point Pi at an
empty directory merely to suppress warnings: its daily-note settings must match
the existing vault. Device keys and API keys stay machine-local, not in Nix.

Syncthing does not merge simultaneous edits to daily notes; avoid concurrent
writes or review any `.sync-conflict-*` files. Until a local vault is configured,
Pi summaries remain queued rather than reaching the journal.

## Apply and verify

Use Omarchy's standalone Home Manager activation from
[the agent deployment guide](omarchy-agents.md#apply), not a macOS rebuild task.
No Mac activation is needed for this host-only service.

```bash
systemctl --user status syncthing.service
syncthing --version
python3 tests/omarchy-syncthing.py --installed
```

Run `python3 tests/omarchy-syncthing.py` for source evaluation without starting a
service. `--installed` additionally checks the active service, the loopback-only
listener, the authenticated local REST API, and the tailnet-only Serve mapping
without modifying configuration. Verify the browser endpoint from the Mac with
`curl --noproxy '*' http://omarchy.taila14c2.ts.net:8384/rest/noauth/health`.
