# Lop on Omarchy

Tracked in Fizzy [#721](https://app.fizzy.do/6284043/cards/721) (installation)
and [#723](https://app.fizzy.do/6284043/cards/723) (Mac configuration parity).

`hosts/omarchy.nix` opts into Lop without changing Omarchy's native desktop.
Its `~/.config/lop/config.toml` uses the same Nix-owned source as the Mac:
`~/dev/src`, scan depth 3, fetch timeout 60 seconds, and `check_processes = false`.
The Lop input is pinned to the revision used by the Mac's installed package,
including sibling `exclusions.toml` support.

The Mac's `prune --yes` command and 60-second interval are mirrored by the
Home Manager-owned `lop.service` and `lop.timer`. Lop's native `lop schedule`
commands only support macOS; on Omarchy use systemd instead:

```bash
systemctl --user status lop.timer lop.service
systemctl --user list-timers lop.timer
journalctl --user -u lop.service -n 30 --no-pager
```

The timer starts on activation/startup and runs every minute. Its oneshot service
cannot overlap itself. Existing Lop integration, dirty/locked-worktree, and
Herdr activity safety gates remain intact. Herdr, Git, Worktrunk, and SSH are
explicitly available in the service PATH. Credentials remain machine-local;
fetches are noninteractive, using Omarchy's existing Git credential helpers.
No Mac SSH socket or credentials are copied. Omarchy already has user lingering
enabled, so the timer does not depend on an open SSH connection.

`~/.config/lop/exclusions.toml` stays writable and host-local, matching the Mac's
ownership. Initial parity copies the Mac's home-relative exclusion paths without
copying its home directory or embedding personal paths in Nix. Review this file
when repositories move or new host-specific exclusions are needed. The scheduled
mode and interval are declared in `hosts/omarchy.nix`; change them there and
reactivate Home Manager rather than using `lop schedule edit` on Linux.

Apply using the standalone procedure in [omarchy-agents.md](omarchy-agents.md).
Home Manager starts new timers automatically. For first provisioning, hold the
timer with a temporary runtime condition **before activation**, then validate a
read-only scan in the scheduled environment before releasing it. A runtime mask
alone is insufficient because the Home Manager unit in `~/.config/systemd/user`
has higher lookup priority.

```bash
runtime="/run/user/$(id -u)/systemd/user/lop.timer.d"
mkdir -p "$runtime"
printf '[Unit]\nConditionPathExists=/run/user/%s/lop-preflight-approved\n' "$(id -u)" > "$runtime/preflight.conf"
systemctl --user daemon-reload
# Build and activate Home Manager as documented in omarchy-agents.md.
python3 tests/lop-omarchy.py --installed --preflight
rm "$runtime/preflight.conf"
rmdir "$runtime"
systemctl --user daemon-reload
systemctl --user start lop.timer
python3 tests/lop-omarchy.py --installed
```

The preflight fetches repositories but does not prune. The installed test checks
policy, exclusions, command, environment, timer cadence, and successful scheduled
execution without initiating additional pruning. A new deployment should wait
for the service's first run to finish before running the final check.

Linux package overrides keep the full test suite enabled while replacing the
fixture's `/bin/cat` with Nix coreutils and serializing flaky executable-fixture
tests. Upstream cleanup is tracked in [#722](https://app.fizzy.do/6284043/cards/722).
