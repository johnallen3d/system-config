# Nix

Manage macOS using [Nix](https://nixos.org/nix/), [nix-darwin](https://github.com/LnL7/nix-darwin) and [Home Manager](https://github.com/nix-community/home-manager).

## Prerequisites

Install Nix:

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
```

Clone `system-config`

```bash
cd ~
mkdir -p dev/src
# install command line tools for git (brute force)
xcode-select --install
git clone https://github.com/johnallen3d/system-config.git
cd system-config
```

Give Terminal.app "Full Disk Access" in System Preferences > Privacy & Security > Privacy > Full Disk Access. This is required for some of the `nix-darwin` system settings to apply successfully.

Install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install `nix-darwin` and initial apply:

```bash
nix \
  --extra-experimental-features "flakes nix-command" \
  run nix-darwin \
  -- switch --flake ~/dev/src/system-config
```

## Apply Changes

```bash
darwin-rebuild switch --option eval-cache false --flake ~/dev/src/system-config/.#
```

## Update Installed Packages

```bash
nix flake update
# or from another directory
pushd ~/dev/src/system-config; nix flake update; nixswitch; popd
```

## TODO

Things I'm not sure how to automate yet:

- creation of `~/bin/bottombar` (link to `sketchybar`)

```bash
ln -s (which sketchybar) $HOME/bin/bottombar
```
