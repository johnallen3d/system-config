---
name: nix-system-config
description: |
  Nix flake configuration for macOS (nix-darwin), NixOS, and Home Manager systems.
  Use when working with: (1) Building or applying system configurations, (2) Adding/modifying 
  packages or programs, (3) Creating or editing Nix modules, (4) Managing dotfiles via 
  home-manager, (5) Configuring darwin services/agents, (6) Working with homebrew casks/brews,
  (7) Any task involving .nix files in this repository.
---

# Nix System Config

Multi-platform Nix flake managing macOS, NixOS, and Home Manager configurations.

## Hosts

| Host           | Platform        | Apply Command |
|----------------|-----------------|---------------|
| m4-mbp         | macOS (darwin)  | `mise update-system` |
| macos-virtual  | macOS (darwin)  | `darwin-rebuild switch --impure --flake .` |
| drummer        | NixOS           | `sudo nixos-rebuild switch --impure --flake .#` |
| xcel           | Debian (HM)     | `home-manager switch -b backup --flake .#"john.allen@xcel" --impure` |
| pi-01          | Debian/Pi (HM)  | `home-manager switch -b backup --flake .#"john.allen@pi-01"` |

## Commands

```bash
# Build without applying
nix build .#darwinConfigurations.m4-mbp.system
nix build .#homeConfigurations."john.allen@pi-01"

# Apply (macOS - repo-local mise task)
mise update-system                         # updates flake first
mise update-system --switch-only           # skip flake update
mise update-system --switch-only --pi-refresh  # also refresh managed Pi packages

# Test single option
nix eval .#darwinConfigurations.m4-mbp.config.services.sketchybar.enable

# Update inputs
nix flake update --commit-lock-file

# Lint
nix flake check
```

## Directory Structure

```
hosts/           # Per-host configs (kebab-case names)
lib/             # Helper functions (make-*-system.nix)
modules/
  common/        # Shared across platforms
  darwin/        # macOS-specific (agents, homebrew, system)
  home-manager/  # User programs/dotfiles
  nixos/         # NixOS-specific
```

## Code Style

- 2-space indentation, no tabs
- Trailing commas consistently
- Use flake inputs (`nixpkgs`, `home-manager`); avoid `import <nixpkgs>`
- Attr ordering: `imports` first, then logical groups (services, programs, environment)
- Host names: kebab-case; variables: snake_case
- Prefer `mkIf` for conditions; avoid nested `if` chains
- Minimize `assert`; use `lib.warn`/`lib.trace` for diagnostics
- Match option schemas; explicit lists; no string concat for paths
- Never commit secrets; use keychain or environment variables

## Adding a Package

Home Manager program (user-level):
```nix
# modules/home-manager/default.nix or relevant submodule
programs.<name>.enable = true;
# or
home.packages = with pkgs; [ package-name ];
```

Darwin system package:
```nix
# modules/darwin/environment/default.nix
environment.systemPackages = with pkgs; [ package-name ];
```

Homebrew (macOS GUI apps):
```nix
# modules/darwin/homebrew/default.nix
homebrew.casks = [ "app-name" ];
homebrew.brews = [ "formula-name" ];
```

## Creating a Module

1. Create `modules/<platform>/<name>/default.nix`
2. Add to imports in parent `default.nix`
3. Use `mkIf` for conditional logic:

```nix
{ config, lib, pkgs, ... }:
{
  options.my.feature.enable = lib.mkEnableOption "my feature";
  
  config = lib.mkIf config.my.feature.enable {
    # configuration here
  };
}
```

## Policy

Never create git commits unless explicitly requested.
