---
description: "Install a Nix package or Pi extension on this standalone Linux host"
argument-hint: "[nix|pi] <package>"
---

Install $ARGUMENTS declaratively. Search nixpkgs first; do not use Homebrew or
macOS rebuild tasks on Linux.

- For CLI tools, add the package alphabetically to
  `modules/home-manager/packages/coding-agents.nix`.
- For Pi extensions, update the appropriate personal/work package specs in
  `modules/home-manager/pi/packages.nix`. Respect `$PI_CODING_AGENT_DIR`.
- Apply from the system-config checkout on Omarchy, without updating inputs:

```bash
. /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
export NIX_CONFIG='extra-experimental-features = nix-command flakes'
nix build --no-write-lock-file \
  'path:.#homeConfigurations."johna@omarchy".activationPackage' --out-link result
./result/activate
```

Do not overwrite unexpected file collisions or change Omarchy's shell/desktop.
Verify the executable and its version. Pi packages are bootstrapped on the next
launch; use `pi-personal list` or `pi-work list` for the intended profile.
