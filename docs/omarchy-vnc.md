# Omarchy VNC over Tailscale

Tracked in [Fizzy #689](https://app.fizzy.do/6284043/cards/689).

Home Manager runs Nix-packaged WayVNC as `johna`'s `wayvnc.service`. It shares
an existing Hyprland desktop; it does not create a separate desktop, enable
login-screen access, or arrange an unattended GUI login.

The service starts with `graphical-session.target`, restarts on failure, and
stops when that session stops. It inherits the GUI environment that Omarchy's
UWSM session imports into the user systemd manager. It retries if the Tailscale
address is not ready yet. No shell, Hyprland, monitor, tray-target, or session
environment configuration is managed here.

## Verified outcome

WayVNC 0.10.2 is enabled and running with its sole listener on
`100.97.112.40:5900`. A direct connection from the Mac over Tailscale passed
RFB 3.8 negotiation, existing-password authentication, and framebuffer delivery
for the 3840×2160 desktop, without an SSH tunnel. Unauthenticated VNC was not
offered. Test pixels were discarded, not displayed or saved. MagicDNS resolved
the host name to the verified Tailscale IPv4 address.

The private config and password remain unchanged. Shell/desktop fingerprints
are preserved. GUI logout/reboot was not performed; the graphical-session
autostart/stop dependency and enablement link were verified instead.

## Connect from macOS

With Tailscale connected, open Screen Sharing directly:

```bash
open 'vnc://100.97.112.40:5900'
```

Or use Omarchy's verified MagicDNS name:

```bash
open 'vnc://omarchy.taila14c2.ts.net:5900'
```

Use the existing WayVNC password, not the SSH/Linux login password. No SSH
tunnel is needed. The service binds only to Omarchy's Tailscale IPv4 address,
`100.97.112.40`, not its LAN address, loopback, IPv6, or all interfaces.
Tailscale provides transport encryption and tailnet access controls. Devices
permitted to reach this host and port by those controls can attempt VNC login;
this change does not narrow your tailnet's ACLs or grants.

## Password configuration

The private `~/.config/wayvnc/config` already existed and is deliberately not
managed by Nix. Its password must never enter this repository or the Nix store.
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
enabled. Edit the password securely on Omarchy if needed, then restart the
service. Legacy VNC/DES authentication supports macOS Screen Sharing but uses
only the first eight password characters and does not itself encrypt desktop
traffic. Tailscale supplies that encryption here; do not expose this config on
a LAN, public address, or wildcard listener.

If the private config is missing, systemd skips starting the service. Restore
it securely on the host; do not use unauthenticated access as a fallback.

## Operations

Run on Omarchy as `johna`:

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
systemctl --user show-environment | grep -E '^(WAYLAND_DISPLAY|XDG_RUNTIME_DIR)='
systemctl --user is-active graphical-session.target
```

Configure through `modules/home-manager/omarchy-vnc.nix`, imported only by
`hosts/omarchy.nix`. If the node is recreated with a different Tailscale IPv4,
update the bind address in that module and rebuild before reconnecting. Build
and activate `johna@omarchy` as in the
[standalone Home Manager guide](omarchy-poc.md); activation reloads and starts
changed user services. No sudo, Arch package removal, or desktop restart is
required. Home Manager owns the unit and autostart link, so do not manually
replace those files or use `systemctl enable/disable` to manage them.
