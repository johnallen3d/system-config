# AGENTS.md
Repo: Nix flake for macOS, NixOS, Home Manager.
Build (darwin): `nix build .#darwinConfigurations.m4-mbp.system`
Build (home): `nix build .#homeConfigurations."john.allen@pi-01"`
Apply macOS: `set -xg NIXPKGS_ALLOW_UNFREE 1; darwin-rebuild switch --impure --flake .`
Apply macOS (fish): `nix-rebuild` (updates flake unless `--switch-only`)
Apply NixOS: `sudo nixos-rebuild switch --impure --flake .#`
Apply Home Manager: `home-manager switch -b backup --flake .#"john.allen@xcel" --impure`
Update inputs: `nix flake update --commit-lock-file`
Test single option: `nix eval .#darwinConfigurations.m4-mbp.config.services.sketchybar.enable`
Lint flake: `nix flake check` (build + eval checks)
Style: Nix indentation 2 spaces; no tabs; consistent trailing commas.
Imports: Use flake inputs (`nixpkgs`, `home-manager`); avoid `import <nixpkgs>`.
Ordering: attrs: `imports`, then logical option groups (services, programs, environment).
Naming: hosts kebab-case; variables snake_case; upstream attr names unchanged.
Modules: prefer `mkIf` for conditions; avoid nested `if` chains.
Errors: minimize `assert`; use `lib.warn` / `lib.trace` for diagnostics.
Types: match option schemas; explicit lists; avoid string concatenations for paths.
Secrets: never commit tokens; externalize via keychain or environment.
Cursor/Copilot rules: none present (.cursor/, .cursorrules, .github/copilot-instructions.md absent).
Queries: opencode subdir uses zen server for DuckDB authoring; see its AGENTS.md.
Policy: Never create a git commit unless explicitly requested by the user.
