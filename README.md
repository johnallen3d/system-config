# Nix

Manage macOS using [Nix](https://nixos.org/nix/), [nix-darwin](https://github.com/LnL7/nix-darwin) and [Home Manager](https://github.com/nix-community/home-manager).

## Install

Install Nix:

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
```

Clone `system-config`

```bash
cd ~
mkdir -p dev/src
git clone ... system-config
cd system-config
```

Install `nix-darwin`:

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
