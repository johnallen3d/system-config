# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Quick Reference

- **Build**: `nix build .#darwinConfigurations.m4-mbp.system`
- **Apply macOS**: `nix-rebuild` (fish) or `darwin-rebuild switch --impure --flake .`
- **Apply NixOS**: `sudo nixos-rebuild switch --impure --flake .#`
- **Lint**: `nix flake check`
- **Update**: `nix flake update --commit-lock-file`

## Policy

Never create git commits unless explicitly requested.
