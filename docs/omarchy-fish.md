# Omarchy Fish

Tracked in [Fizzy #696](https://app.fizzy.do/6284043/cards/696).

## Use it

New Herdr panes use Nix-managed Fish. Existing panes keep their running shell;
open a new tab, or run `exec ~/.nix-profile/bin/fish` in an idle shell.
From an ordinary SSH or desktop terminal, use the same command:

```bash
exec ~/.nix-profile/bin/fish
```

The account's login shell remains `/usr/bin/bash`. This avoids changing
Omarchy's login/session bootstrap or requiring sudo. Bash startup files,
Ghostty, Hyprland, Omarchy themes and the existing Bash Starship config are not
managed or modified by this module. To launch Fish directly in Ghostty without
changing the account login shell, add this to your **user-owned** Ghostty config
and reload it:

```ini
command = /home/johna/.nix-profile/bin/fish
```

That terminal opt-in is not applied automatically.

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
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' \
  --out-link result-fish
DRY_RUN=1 ./result-fish/activate
./result-fish/activate
~/.local/bin/herdr server reload-config
python3 tests/omarchy-fish.py
```

Do not force unexpected file collisions or use automatic backups to overwrite
an existing Fish/Television configuration. Build and review the dry run first.
Reloading Herdr affects new panes only; it does not interrupt running agents.

Live verification passed on Omarchy, including repeat activation, shell/helper
checks and unchanged fingerprints for Bash, Bash Starship, Hyprland, Ghostty and
Omarchy configuration. No account login-shell change was made.

To remove the opt-in, remove the Fish module import, rebuild and activate the
host profile, then reload Herdr. New Herdr panes fall back to the existing
Bash wrapper; do not uninstall the entire Home Manager profile, which also owns
agents and services. See the [standalone guide](omarchy-poc.md).
