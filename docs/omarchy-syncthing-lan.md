# Omarchy Syncthing: restricted LAN GUI

Tracked in [Fizzy #745](https://app.fizzy.do/6284043/cards/745).
For pairing, vault capture, and existing Tailscale access, see
[the Syncthing guide](omarchy-syncthing.md).

## Managed endpoint

`hosts/omarchy.nix` imports `omarchy-syncthing-lan.nix`, only on Omarchy.
Its Nix-managed `syncthing-lan.service` forwards **192.168.4.26:8384** to the
unchanged loopback GUI using socat. It binds that IPv4 address explicitly, not
`0.0.0.0`, IPv6, or Tailscale. socat's `range=192.168.5.11/32` rejects all sources
except **pi-01**. The existing Tailscale URL and Serve mapping remain unchanged.

At startup, the service verifies machine-local GUI credentials exist and that an
unauthenticated request to `/rest/config` returns 401/403. Credentials, API keys,
folders, and devices remain Syncthing-owned; none are copied into the Nix store
or logs. Do not disable GUI authentication while the forwarder runs. HTTP bytes
(including authentication) pass unchanged: this LAN hop is **not encrypted**.
Use it only on the trusted home LAN, never across untrusted networks. The future
Caddy HTTPS route protects the browser-to-proxy hop, not this upstream hop.
The existing host-header exception is retained for Tailscale Serve and the future
proxy; the loopback bind, source restriction, firewall, and GUI authentication
remain the access controls. No extra host-header bypass is added.

## Address and firewall prerequisites (operator action)

The observed `192.168.4.26/22` is DHCP-assigned. **John confirmed the DHCP
reservation** for Omarchy's `192.168.4.26` after deployment. Its `enp3s0` MAC is
`84:47:09:92:02:74`; pi-01 currently uses `192.168.5.11`. Keep both addresses stable.
Do not readdress Omarchy or change subnets as part of this card. If its address
changes, the forwarder fails to bind and retries; update the reservation rather
than replacing the explicit bind with a wildcard.

UFW is enabled. John added the narrow 8384 allowance; its saved rule is verified:
`-i enp3s0 -p tcp -d 192.168.4.26 --dport 8384 -s 192.168.5.11 -j ACCEPT`.
Live kernel rule inspection still requires interactive sudo. Home Manager does not manage Arch's
root firewall; its persistent native UFW rule is a separate deployment step.
On Omarchy, inspect live rules **before** adding the source-specific allowance:

```bash
sudo ufw status verbose
sudo ufw status numbered
sudo ufw allow in on enp3s0 proto tcp from 192.168.5.11 to 192.168.4.26 port 8384 comment 'Syncthing GUI from pi-01 only'
sudo ufw status verbose
```

Review/remove any existing broader 8384 allowance rather than adding one. Keep
other service rules unchanged. Do not open router ports, enable Funnel, allow
the whole LAN, or run `ufw reset`. Both UFW's rule and socat's source filter must
remain in place. Saved firewall rules alone do not prove the effective kernel
rules; the operator's sudo inspection and the pi-01 connection test are required.

## Direct LAN return route (#746)

Post-firewall testing exposed a separate routing blocker, tracked in
[Fizzy #746](https://app.fizzy.do/6284043/cards/746). pi-01 sends to Omarchy directly
through `eth0` from `192.168.5.11`, and resolves Omarchy's correct MAC. However,
Omarchy accepts Tailscale's `192.168.5.0/24` subnet route in table 52. Its priority
5270 rule wins over the main table's directly connected `192.168.4.0/22` route.
Before the exception below, `ip -4 route get 192.168.5.11 from 192.168.4.26`
selected `tailscale0`, causing an asymmetric connection. The UFW allowance alone
was insufficient.

The applied fix is a **destination-only pi-01 /32 policy rule** on
Omarchy's existing wired NetworkManager profile. Do not disable all accepted
Tailscale routes, prefer main for all traffic, or change addresses/subnets.
The inspected profile is `Wired connection 2`, UUID
`f8ff9eb7-0d58-3b21-bc76-6649a6005a4b`. John applied the rule and reapplied the
profile without cycling the link. Both saved `ipv4.routing-rules` and active
kernel policy now contain priority 2500 selecting main for pi-01. The commands
below document the configuration used; **it is already installed, so do not
append it again**. Operator sudo is required for changes:

```bash
nmcli -g ipv4.routing-rules connection show 'Wired connection 2'
ip -4 rule show
sudo nmcli connection modify 'Wired connection 2' +ipv4.routing-rules 'priority 2500 to 192.168.5.11/32 table 254'
sudo nmcli device reapply enp3s0
ip -4 route get 192.168.5.11 from 192.168.4.26
```

The final route must select `enp3s0`, not `tailscale0`. NetworkManager stores the
exception across reconnects/reboot, and `device reapply` applies it without
cycling the link. If reapply fails, stop and inspect rather than bringing down an
active agent host's connection. Keep unrelated profile rules/routes unchanged;
do not append the same rule repeatedly. Then rerun the pi-01 checks below.
See [Tailscale's overlapping LAN/subnet routing guidance](https://tailscale.com/docs/reference/troubleshooting/network-configuration/lan-traffic-overlapping-subnets).

Routing rollback removes only this appended exception, retaining the rest of
the profile:

```bash
sudo nmcli connection modify 'Wired connection 2' -ipv4.routing-rules 'priority 2500 to 192.168.5.11/32 table 254'
sudo nmcli device reapply enp3s0
```

## Activation and verification

Transfer only intended files to Omarchy's active working-tree snapshot after
checking for divergence. Preserve its existing lockfile and unrelated changes.
Use [standalone Home Manager activation](omarchy-agents.md#apply); no Mac rebuild
is needed. This adds a forwarder without changing Syncthing's daemon listener
or synchronization settings.

```bash
python3 tests/omarchy-syncthing.py
python3 tests/omarchy-syncthing-lan.py
# After Home Manager activation:
python3 tests/omarchy-syncthing.py --installed
systemctl --user status syncthing.service syncthing-lan.service
```

The source regression checks Mac exclusion and the exact listener/filter. Linux
also runs a synthetic socat fixture proving permitted sources forward and others
are rejected. Installed checks verify the actual forwarder listener, source
filter, backend authentication, and existing Syncthing/Tailscale behavior.

From pi-01, run `python3 tests/omarchy-syncthing-lan.py --lan-client` using a copy
of that test and `modules/home-manager/omarchy-syncthing/check-auth.py`. Or:

```bash
curl --noproxy '*' --fail --connect-timeout 10 http://192.168.4.26:8384/rest/noauth/health
curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}\n' http://192.168.4.26:8384/rest/config
```

Health must return `{"status":"OK"}`; protected configuration must return 401/403.
Verify normal GUI sign-in in a browser through pi-01 (not a general LAN client),
and recheck the existing Tailscale URL from a tailnet device. Do not put passwords
in curl arguments, terminal logs, or Git. Confirm paired devices/folders and sync
status are unchanged. Repeat installed/client checks after an operator-approved
reboot; do not reboot an active agent host automatically.

**Deployment status:** the Home Manager forwarder is activated on Omarchy.
Installed checks and the Linux source-filter regression pass; the unchanged
Tailscale health URL works. Syncthing was not restarted and its device, folder,
GUI, and file-transfer configuration fingerprint is unchanged. Omarchy's older
lockfile was preserved. No Mac activation is needed for this host-only change.

**Network verification passed:** pi-01 reaches LAN health and the GUI page;
unauthenticated `/rest/config` returns 403 with either the LAN-IP Host header or
the future `sync-omarchy.jallen7usa.com` Host header. The latter is an upstream
header test only, not a DNS/Caddy deployment. NetworkManager's saved rule and
kernel policy prefer `enp3s0` for pi-01, resolving #746. Tailscale health still
works; the synced folder is idle with zero needed bytes/pull errors. Configuration
is unchanged. John confirmed the DHCP reservation; the exact UFW rule is saved.

**Remaining acceptance check:** normal browser sign-in with John's existing GUI
credentials. #745 stays open until that is confirmed. No reboot was performed;
service enablement/lingering and the saved UFW/NetworkManager configuration are
verified, with post-reboot checks available for the next planned reboot. This card does not deploy
Caddy, change DNS, or update Glance; those follow only after the host-side endpoint
is verified, with a LAN upstream (never an Omarchy Tailscale upstream).

## Browser sign-in check

The source filter intentionally prevents a direct connection from a general LAN
client. From the Mac, temporarily tunnel through the allowed pi-01 host:

```bash
ssh -N -L 127.0.0.1:18384:192.168.4.26:8384 pi-01
```

Open `http://127.0.0.1:18384` locally and sign in using the existing Syncthing GUI
credentials. Do not share the password with an agent. Stop the tunnel with Ctrl-C
when finished. This adds no persistent proxy, listener on another interface, or
DNS/Caddy configuration; the connection to Omarchy still originates from pi-01.

## Rollback

For immediate containment: `systemctl --user stop syncthing-lan.service`.
Remove the `omarchy-syncthing-lan.nix` import from `hosts/omarchy.nix`, then
build/activate Home Manager again to remove the unit permanently. Remove only
this UFW rule with interactive sudo:

```bash
sudo ufw delete allow in on enp3s0 proto tcp from 192.168.5.11 to 192.168.4.26 port 8384
```

Leave `syncthing.service`, its writable configuration, and the existing Tailscale
Serve mapping untouched. Recheck synchronization and the tailnet health URL.
