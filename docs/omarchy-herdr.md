# Omarchy Herdr

Tracked in [Fizzy #695](https://app.fizzy.do/6284043/cards/695).

## Use it

The Mac's existing Herdr sidebar has an enabled **Omarchy** machine pointing to
`johna@omarchy`, session `default`. Select it to work on the Linux box. Local
workspaces remain on the Mac; remote shells, agents, repositories and builds run
on Omarchy. Closing a client or losing SSH leaves remote processes running.

For a dedicated remote window, run this from an ordinary Mac terminal (not from
inside an existing Herdr pane):

```bash
herdr --remote johna@omarchy
```

At Omarchy's desktop, or after ordinary SSH, attach with:

```bash
~/.local/bin/herdr
```

Use that explicit path outside managed panes: Omarchy deliberately puts
`/usr/bin` before user tools, so bare `herdr` there still resolves to the
untouched Arch package (0.8.2). Nix provides 0.9.3 at `~/.local/bin/herdr`;
Mac remote discovery finds this compatible installation without changing PATH
or removing the Arch package. Inside newly created Herdr panes, Nix/user tools
come first. The Mac UI uses its Mac keybindings and theme; a Linux-local client
keeps the existing Linux keybindings, including `ctrl+space` as prefix and
`prefix+d` to detach.

Use `pi-personal`, `pi-work`, and `claude-work` as in the
[agent guide](omarchy-agents.md). Named launchers set both
`PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`. New remote panes default to the
personal pair; personal Claude remains intentionally dormant. No credentials,
sessions or repositories are copied from the Mac.

## Nix ownership

`hosts/omarchy.nix` opts into `modules/home-manager/omarchy-herdr.nix`:

- Nix Herdr, fzf, Worktrunk and the linked-worktree helper.
- The same pinned project-picker and Worktrunk plugins as the Mac.
- Herdr's package-versioned skill in global, personal/work Pi and work Claude
  locations; personal Claude uses the global skills directory.
- Pi and Claude integrations installed separately into all four profiles.
- The reviewed original Linux Herdr config, with a managed shell wrapper.
  When the [Fish module](omarchy-fish.md) is enabled, new panes use the shared
  Fish configuration, including Worktrunk's directory-changing function.
  Without Fish, the wrapper falls back to the existing `.bashrc` plus managed
  PATH and Worktrunk integration. Bash startup files remain untouched.
  Config reload affects new panes; open a new tab in an already-running session.
- A `herdr.service` user unit owning the headless `default` session. It starts
  with the user manager, not the graphical session, and restarts on failure.
  It opens only local Unix sockets; remote access uses existing SSH.

The original config was preserved at
`~/.cache/herdr/pre-home-manager-config.toml`. Initial migration accepts only
an exact match to the reviewed config; unexpected edits or collisions fail.
Plugins, settings integrations and runtime catalogs remain writable where
Herdr requires them. Authentication files remain unmanaged.

Linux user lingering was enabled with `loginctl enable-linger johna`, outside
Home Manager. It allows the user manager to start at boot and survive the last
logout. This is the one host-level setting: standalone Home Manager cannot own
it. On a recreated box, enable it with the host's required authorization.
Omarchy's sleep policy is unchanged: a suspended or powered-off box cannot do
work. Running processes do not survive reboot; Herdr's saved-session restoration
is not a guarantee that an agent resumes its in-flight task.

On the Mac, `hosts/m4-mbp.nix` imports `herdr-omarchy-client.nix`. Its activation
uses the Nix-managed `herdr-omarchy-setup` helper to seed one `Omarchy` connection
in each local named session:

- Local `personal` connects to remote `default`, preserving its existing panes
  and the Home Manager-managed remote service.
- Local `work` connects to remote `work`, with independent workspaces and panes.

Upstream Herdr 0.9.3 shares a machine catalog across all local sessions. The Mac
Nix package carries a small patch to scope both the catalog and saved selection
under `~/.local/state/herdr/sessions/<local-session>/client/`. Default-session
clients retain the original global catalog. Server sockets, config, plugins, and
pane processes are unchanged. Existing clients must **detach with `ctrl+b q` and
reattach** (`herdr session attach personal` / `herdr session attach work`) to load
the patched client; do not stop their servers. Reloading config cannot change the
old client's catalog path.

The helper uses the supported CLI and preserves existing per-session profile
IDs, unrelated machines, and disabled state. It never approves an installer or
server replacement. An unavailable box defers setup without breaking the Mac
rebuild; retry with `herdr-omarchy-setup`. Catalogs remain user-owned, not read-only
Home Manager files. Removing a profile allows the next activation to seed it
again; disable it if you want it retained but disconnected. The remote `work`
daemon is started by setup, not owned by the default-session systemd service.

## Apply and operate

Apply Omarchy from its system-config checkout as `johna`, without updating inputs:

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' --out-link result-herdr
./result-herdr/activate
~/.local/bin/herdr server reload-config
```

Apply the Mac with `mise update-system --switch-only`, then detach and reattach
existing clients once to activate catalog isolation. Later machine additions are
picked up by patched clients without restarting or changing their selection.

On Omarchy:

```bash
systemctl --user status herdr.service
~/.local/bin/herdr status server
loginctl show-user johna -p Linger
journalctl --user -u herdr.service -b -n 40 --no-pager
```

Package/unit changes deliberately do **not** automatically restart an active
server: doing so would kill its shells and agents. Once work is finished, an
explicit `systemctl --user restart herdr.service` uses the new binary. To stop
this managed session, use `systemctl --user stop herdr.service`; starting it
again uses `systemctl --user start herdr.service`. Do not stop it merely because
client and server versions differ; compatibility is negotiated.

From a Mac Herdr pane, discover remote IDs before controlling them:

```bash
herdr --session personal machine status Omarchy --json
herdr --session work machine status Omarchy --json
# In a named session, inherited context selects its own Omarchy connection.
herdr --machine Omarchy workspace list
herdr --machine Omarchy agent list
```

UI machine selection does not retarget commands running in an existing pane.
Always use `--machine Omarchy` for remote control from a local pane.

## Verification

Deployment verified Nix Herdr 0.9.3, enabled/active user service, `Linger=yes`,
reachable saved-machine access, both enabled plugins, and current Pi/Claude
integrations in each explicit profile. Existing coding-agent/work-kit tests
passed. Shell/desktop file fingerprints were unchanged. No reboot, GUI logout,
suspend, or model prompt was performed.

Run the remote smoke test from a **Mac Herdr pane**:

```bash
python3 tests/herdr-omarchy.py
```

It creates its own unfocused remote workspace, verifies a delayed shell process
across independent SSH API connections, personal profile defaults, Nix PATH,
Worktrunk's shell function and Pi detection, then closes only that workspace.
No model call is made.

## Rollback

Before activation, retain the previous generation path. This deployment saved
it at `~/.cache/herdr/previous-generation`. After finishing remote work, stop the
managed service, then run that generation's `activate` script. Active unit
changes are deliberately protected from automatic stopping/restarting, so do
not skip the explicit stop when removing the service. Restore the reviewed
original Herdr config from its backup only after Home Manager no longer owns
the destination. Profile credentials, sessions and plugin runtime data remain.

Removing/disablement of the Mac machine profile disconnects its client only; it
does not stop Omarchy's server. To undo lingering, use the host-authorized
`loginctl disable-linger johna`; review other user services before doing so.
