Nix

Manage macOS using [Nix](https://nixos.org/nix/), [nix-darwin](https://github.com/LnL7/nix-darwin) and [Home Manager](https://github.com/nix-community/home-manager).

## Prerequisites

Set hostname to a known (configured) value:

- m1-mpb
- macos-virtual

Install Nix:

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
```

Install command line tools for git (brute force):

```bash
xcode-select --install
```

~Give Terminal.app "Full Disk Access" in System Preferences > Privacy & Security > Privacy > Full Disk Access. This is required for some of the `nix-darwin` system settings to apply successfully.~ I've [disabled this](https://github.com/johnallen3d/system-config/commit/e3274eb53b74653790df34cf5ad0790fdfadd20e) for now.

Install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Clone `system-config`

```bash
mkdir -p ~/dev/src
cd ~/dev/src
git clone https://github.com/johnallen3d/system-config.git
cd system-config
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
# on macOS
set -xg NIXPKGS_ALLOW_UNFREE 1; darwin-rebuild switch --impure --flake ~/dev/src/system-config/

# on NixOS
sudo nixos-rebuild switch --flake ~/dev/src/system-config/.# --impure

# on Debian/Pi (using home-manager)
home-manager switch -b backup --flake ~/dev/src/system-config/.#john.allen@pi-01

# on Debian/Orb (using home-manager)
home-manager switch -b backup --flake ~/dev/src/system-config/.#john.allen@xcel --impure
```

## Update Installed Packages

```bash
nix flake update --commit-lock-file
# or from another directory
pushd ~/dev/src/system-config; nix flake update --commit-lock-file; nixswitch; popd
```
## TODO

Things I'm not sure how to automate yet:

- [ ] creation of `~/bin/bottombar` (link to `sketchybar`)

```bash
ln -s (which sketchybar) $HOME/bin/bottombar
```

- [ ] set the users default shell to `fish`

```bash
chsh -s /run/current-system/sw/bin/fish
```

- [ ] setup `op`, login and `gh` plugin
- [ ] can I add `$HOME` to Finder Favorites (sidebar)? - this seems to be stored in a binary file [here](~/Library/Application Support/com.apple.sharedfilelist/com.apple.LSSharedFileList.FavoriteItems.sfl3):
- [ ] can I add "login items"? - possibly via [plist files](https://stackoverflow.com/a/7643260/407530)?
- [x] debug lsd fonts
- [ ] debug services (bars, mpd)
- [x] debug Neovim setup
- [ ] automate install of [SketchyBar Lua Plugin](https://github.com/FelixKratz/SbarLua?tab=readme-ov-file#sketchybar-lua-plugin)
- [ ] Music?
- [ ] Photos?
- [ ] how to correctly set "allow unfree" specifically for `tart`
