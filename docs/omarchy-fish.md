# Omarchy Fish

Tracked in [Fizzy #696](https://app.fizzy.do/6284043/cards/696), with the account
default-shell correction in [#697](https://app.fizzy.do/6284043/cards/697).

## Use it

Fish must be the **account login shell**, not merely a Herdr pane setting.
After Home Manager activation, run the installed helper once as `johna`:

```bash
~/.nix-profile/bin/omarchy-fish-default-shell
```

Authorize its sudo prompt. It idempotently registers
`/home/johna/.nix-profile/bin/fish` in `/etc/shells` and sets that path as
`johna`'s account shell with Arch's `chsh`. The stable profile path follows
Fish package upgrades; do not use a versioned `/nix/store` path. Standalone
Home Manager cannot change the account database through user activation.
The helper does not grant passwordless sudo or edit authentication policy.

Fresh SSH logins then start Fish. Log out and back into the desktop once so
applications inherit the new account shell instead of a cached Bash `SHELL`.
New Herdr panes also use Fish. Existing shells keep running; replace an idle
one with `exec ~/.nix-profile/bin/fish`, or open a new terminal. No Ghostty
override is required: leave its default shell selection alone.

Fish initializes Nix and imports `OMARCHY_PATH` and `PATH` from Omarchy's
native bootstrap for login and noninteractive SSH command shells. Bash startup
files, Ghostty, Hyprland, Omarchy themes and Bash's Starship config stay intact.

## What is shared

`hosts/omarchy.nix` imports `modules/home-manager/omarchy-fish.nix`, which reuses
our shared Fish and Starship modules without the shared desktop/package suite:

- Rose Pine Fish syntax colors, `done`, and colored man pages.
- Starship prompt/transience in `~/.config/fish/starship.toml`, separate from
  Omarchy's `~/.config/starship.toml`.
- Shared aliases, `ls`/`ll`/`la` via lsd, `mkdir` then cd, bang/dollar bindings,
  `glow-watch`, and Linux-safe `ip` (arguments are forwarded to iproute2).
- Worktrunk's cd-aware function and completions, zoxide, nix-your-shell,
  Television's Ctrl-T/Ctrl-R integration and shared picker config.
- Omarchy's native mise activation and Neovim. Optional `leadr` integration
  runs only when installed; this module does not install it.
- Nix/user tools retain PATH precedence across mise directory changes. Startup
  removes transient npx shims and preserves inherited `PI_CODING_AGENT_DIR` and
  `CLAUDE_CONFIG_DIR`; it does not copy credentials or change selected profiles.

Mac-only application paths and clipboard aliases are excluded on Linux. The
Linux `uuid` alias prints the UUID rather than requiring a clipboard session.
Some shared aliases still target optional tools (such as kubecolor); invoking
those requires their own package installation.

## Apply and verify

Run on Omarchy as `johna`, from its system-config checkout/snapshot:

```bash
NIX_CONFIG='extra-experimental-features = nix-command flakes' \
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result-fish
DRY_RUN=1 ./result-fish/activate
./result-fish/activate
~/.nix-profile/bin/omarchy-fish-default-shell
~/.local/bin/herdr server reload-config
python3 tests/omarchy-fish.py

# Read-only confirmation; no sudo needed.
~/.nix-profile/bin/omarchy-fish-default-shell --check
getent passwd johna
```

Do not force unexpected file collisions or use automatic backups to overwrite
an existing Fish/Television configuration. Build and review the dry run first.
Reloading Herdr affects new panes only; it does not interrupt running agents.

The original Fish installation passed live shell/helper and repeat activation
checks, but incorrectly left the account shell as Bash. The default-shell
correction additionally requires `/etc/shells` registration, an account database
check and fresh SSH/login verification; helper installation alone is not proof
that the account change has been authorized.

## Revert safely

**Before removing Fish from Home Manager**, restore a valid installed shell:

```bash
sudo /usr/bin/chsh -s /usr/bin/bash johna
getent passwd johna
```

Then remove the Fish module import, rebuild and activate the host profile,
and reload Herdr. New Herdr panes fall back to the existing
Bash wrapper; do not uninstall the entire Home Manager profile, which also owns
agents and services. See the [standalone guide](omarchy-poc.md).
