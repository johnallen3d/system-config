---
name: pi-nix-integration
description: Manage pi packages, skills, and themes within this nix-darwin system-config project. Use when adding pi packages to nix config, managing local skills, or understanding pi integration in this project.
---

# Pi Nix Integration

This skill manages pi packages, extensions, skills, and themes within the nix-darwin system-config project.

## Key Difference from Standard Pi

**Standard pi workflow**: `pi install npm:package-name` 

**This project workflow**: Pi packages are declared in nix configuration and installed automatically on first pi run.

## Architecture

### Pi Package Management
- **Declaration**: `modules/home-manager/packages/pi.nix`
- **Auto-installation**: Packages install on first pi command run
- **Tracking**: Uses pi's native package management but declared in nix
- **Location**: Packages install to `~/.local/lib/node_modules/`

### Current Integration Method
```nix
{pkgs, ...}: let
  piPackages = [
    "pi-prompt-template-model"
    "pi-subagents" 
    "@tmustier/pi-skill-creator"
  ];
  
  installPiPackages = pkgs.writeShellScript "install-pi-packages" ''
    for package in ${toString piPackages}; do
      ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@0.66.1 install npm:$package 2>/dev/null || true
    done
  '';
in
pkgs.writeShellScriptBin "pi" ''
  # Ensure pi packages are installed on first run
  if [ ! -f "$HOME/.pi/packages-installed" ]; then
    echo "Installing pi packages..."
    ${installPiPackages}
    touch "$HOME/.pi/packages-installed"
  fi
  
  exec ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@0.66.1 "$@"
''
```

## Smart Package Installation

### Quick Install Command
Use the project's `/pkg-install` command for intelligent package management:

```bash
/pkg-install package-name
```

This command will:
1. Research the package across nixpkgs, homebrew, and pi sources
2. Determine the optimal installation method  
3. Update the appropriate nix configuration file
4. Execute the installation automatically

### Manual Package Addition

For manual control, follow these steps:

### 1. Update Nix Configuration
Edit `modules/home-manager/packages/pi.nix` and add the package name to the `piPackages` list:

```nix
piPackages = [
  "pi-prompt-template-model"
  "pi-subagents" 
  "@tmustier/pi-skill-creator"
  "new-package-name"  # ← Add here
];
```

### 2. Apply Changes
```bash
sudo darwin-rebuild switch --flake ".#m4-mbp" --impure
```

### 3. Trigger Installation
Remove the marker file to force reinstallation:
```bash
rm -f ~/.pi/packages-installed
pi list  # This will install all packages including new ones
```

## Local Skills Management

### Project-Local Skills
- **Location**: `.agents/skills/` (this directory)
- **Scope**: Available only within this project
- **Priority**: Takes precedence over global skills with same name

### Creating Local Skills
```bash
mkdir -p .agents/skills/my-skill
# Create SKILL.md with proper frontmatter
```

### Global vs Local Skills
- **Global**: `~/.pi/agent/skills/` - available everywhere
- **Project**: `.agents/skills/` - available in this project only
- **Package**: `skills/` in installed packages

## Verification Commands

### Check Pi Package Status
```bash
pi list                    # List all installed packages
which pi                   # Should show nix-managed path
```

### Check Skill Loading
```bash
pi --no-skills            # Start without skills
pi --skill /path/to/skill # Test specific skill
/reload                   # Reload skills after changes
```

## Troubleshooting

### Pi Command Not Found After Nix Rebuild
```bash
# Clear npx cache if old pi version is cached
rm -rf ~/.npm/_npx
exec $SHELL  # Reload shell
```

### Force Package Reinstallation
```bash
rm -f ~/.pi/packages-installed
pi list  # Will reinstall all declared packages
```

### Skill Not Loading
- Check frontmatter format in SKILL.md
- Verify directory name matches `name` field
- Use `/skill:name` to invoke explicitly
- Check for syntax errors with `/reload`

## Integration Benefits

**Declarative**: Pi packages declared alongside other system packages
**Reproducible**: Same pi setup across machines using this config
**Versioned**: Pi package list tracked in git
**Consistent**: Follows project's nix-first approach

This approach maintains pi's native package management while gaining nix's reproducibility and declarative configuration benefits.