# AGENTS.md

Nix flake for macOS (nix-darwin), NixOS, and Home Manager.

## Quick Reference

- **Build**: `nix build .#darwinConfigurations.m4-mbp.system`
- **Apply macOS**: `nix-rebuild` (fish) or `darwin-rebuild switch --impure --flake .`
- **Apply NixOS**: `sudo nixos-rebuild switch --impure --flake .#`
- **Lint**: `nix flake check`
- **Update**: `nix flake update --commit-lock-file`
- **Search packages**: `nix search nixpkgs <name>`

## Adding Packages

**Preference order**: nix packages > homebrew

**Package locations**:
- `modules/home-manager/packages/default.nix` - General packages (all platforms)
- `modules/home-manager/packages/darwin.nix` - macOS-only packages
- `modules/home-manager/packages/linux.nix` - Linux-only packages

**Process**:
1. Search nixpkgs first: `nix search nixpkgs <package-name>`
2. Add to appropriate file in `home.packages` list (alphabetically sorted)
3. Build to verify: `nix build .#darwinConfigurations.m4-mbp.system`

## Policy

Never create git commits unless explicitly requested.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:

   ```bash
   git pull --rebase
   bd sync
   ```

5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**

- ALWAYS say "ready to push when you are" - YOU must NOT push
