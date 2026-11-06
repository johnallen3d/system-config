# Omarchy VNC over Tailscale

Tracked in [Fizzy #689](https://app.fizzy.do/6284043/cards/689); virtual
output and Miller in [#952](https://app.fizzy.do/6284043/cards/952); Drummer in
[#958](https://app.fizzy.do/6284043/cards/958).

Home Manager runs Nix-packaged WayVNC as `johna`'s `wayvnc.service` on every
Omarchy host (`omarchy`, `miller`, and `drummer`). It does not enable login-screen access or
arrange an unattended GUI login; a Hyprland session must be running.

## Virtual `VNC` output

WayVNC shares a dedicated Hyprland **headless output named `VNC`** (1920×1080,
its own workspace), not a physical monitor. Before each start the unit runs
`hyprctl output create headless VNC` unless an output with that name already
exists, then starts `wayvnc --output=VNC`.

This exists because physical monitors can disappear: Miller's Acer DisplayPort
monitor disconnects when DPMS puts it to sleep, Hyprland removes `DP-10`, and
WayVNC exits with "No fallback outputs left". It exits **0**, so the unit uses
`Restart=always` (with `StartLimitIntervalSec=0`), not `on-failure`. Omarchy
previously relied on the same output created by hand; it is now declared. To see
the physical desktop, move windows/workspaces to `VNC` from the remote session.

The service starts with `graphical-session.target` and stops with it. It
inherits the GUI environment (`HYPRLAND_INSTANCE_SIGNATURE`, `WAYLAND_DISPLAY`)
that Omarchy's UWSM session imports into the user systemd manager, and calls
Omarchy's `/usr/bin/hyprctl`. It retries if the Tailscale address is not ready
yet. No shell, Hyprland config, physical monitor, tray-target, or session
environment configuration is managed here.

## Verified outcome

WayVNC 0.10.2 listens only on each host's Tailscale IPv4: `omarchy`
`100.97.112.40:5900`, `miller` `100.113.199.114:5900` (both reachable from the
Mac with physical monitors asleep, 2026-11-05). On Omarchy, a direct connection from the Mac over Tailscale passed
RFB 3.8 negotiation, existing-password authentication, and framebuffer delivery
for the then-shared 3840×2160 desktop, without an SSH tunnel. Unauthenticated VNC was not
offered. Test pixels were discarded, not displayed or saved. MagicDNS resolved
the host name to the verified Tailscale IPv4 address.

The private config and password remain unchanged. Shell/desktop fingerprints
are preserved. GUI logout/reboot was not performed; the graphical-session
autostart/stop dependency and enablement link were verified instead.

## Connect from macOS

With Tailscale connected, open Screen Sharing directly:

```bash
open 'vnc://omarchy.taila14c2.ts.net:5900'   # or vnc://100.97.112.40:5900
open 'vnc://miller.taila14c2.ts.net:5900'    # or vnc://100.113.199.114:5900
```

Use that host's WayVNC password, not the SSH/Linux login password. No SSH
tunnel is needed. Each service binds only to its host's Tailscale IPv4 address,
not its LAN address, loopback, IPv6, or all interfaces.
Tailscale provides transport encryption and tailnet access controls. Devices
permitted to reach this host and port by those controls can attempt VNC login;
this change does not narrow your tailnet's ACLs or grants.

## Password configuration

The private `~/.config/wayvnc/config` is host-local and deliberately not
managed by Nix (on Miller it was written with a silent password prompt). Its password must never enter this repository or the Nix store.
Keep its permissions at `0600`. Its current non-secret settings are:

```ini
address=127.0.0.1
port=5900
enable_auth=true
relax_encryption=true
allow_broken_crypto=true
```

The service overrides that legacy file address with the verified Tailscale IP,
so the file and password can remain unchanged. Keep port 5900 and authentication
enabled. Edit the password securely on the host if needed, then restart the
service. Legacy VNC/DES authentication supports macOS Screen Sharing but uses
only the first eight password characters and does not itself encrypt desktop
traffic. Tailscale supplies that encryption here; do not expose this config on
a LAN, public address, or wildcard listener.

If the private config is missing, systemd skips starting the service. Restore
it securely on the host; do not use unauthenticated access as a fallback.

## Operations

Run on the host as `johna`:

```bash
systemctl --user status wayvnc.service
systemctl --user restart wayvnc.service
systemctl --user stop wayvnc.service
systemctl --user start wayvnc.service
tailscale ip -4
ss -ltn 'sport = :5900'
journalctl --user -u wayvnc.service -b -n 40 --no-pager
```

For GUI-environment trouble, inspect only the relevant manager variables:

```bash
systemctl --user show-environment | grep -E '^(HYPRLAND_INSTANCE_SIGNATURE|WAYLAND_DISPLAY|XDG_RUNTIME_DIR)='
systemctl --user is-active graphical-session.target
hyprctl monitors all | grep -E '^Monitor|dpmsStatus'   # expect a "VNC" monitor
```

Configure through `modules/home-manager/omarchy-vnc.nix`, imported by
`hosts/omarchy-common.nix`. Each host file sets its bind address with
`omarchyVnc.address`; if a node is recreated with a different Tailscale IPv4,
update it there and deploy before reconnecting (see
[the Omarchy agents guide](omarchy-agents.md#apply)); activation reloads and
starts changed user services, dropping any connected VNC session. No sudo, Arch package removal, or desktop restart is
required. Home Manager owns the unit and autostart link, so do not manually
replace those files or use `systemctl enable/disable` to manage them.
