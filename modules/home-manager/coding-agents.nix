# Reuse the Mac's agent resources without importing its shell/desktop dotfiles.
{
  lib,
  pkgs,
  ...
}: let
  jq = "${pkgs.jq}/bin/jq";
  claudeDefaults = {
    model = "opus";
  };
in {
  imports = [
    ./packages/coding-agents.nix
    ./agent-projects.nix
    ./claude-prompts.nix
    ./pi-extensions.nix
    ./pi-prompts.nix
    ./pi-settings.nix
  ];

  codingAgents = {
    enableCrossProfileUsageFooter = false;
    enableLegacyHarnessBridges = false;
  };

  home.file = {
    ".config/pi/prompts/pkg-install.md".source = lib.mkForce ./agent-prompts/pkg-install-linux.md;
    ".config/claude-personal/commands/pkg-install.md".source = lib.mkForce ./agent-prompts/pkg-install-linux.md;
    ".config/claude-personal/CLAUDE.md".text = ''
      ALWAYS RESPOND IN ENGLISH. The user's name is John.
      This is standalone Home Manager on Arch/Omarchy, not macOS or NixOS.
      Respect CLAUDE_CONFIG_DIR and PI_CODING_AGENT_DIR; keep profiles separate.
      Never run macOS rebuild tasks here or change Omarchy shell/desktop settings.
      See docs/omarchy-agents.md in system-config for application and authentication.
    '';
    ".config/claude-personal/keybindings.json".source = ./dotfiles/config/claude-personal/keybindings.json;
    ".config/claude-gmatter/keybindings.json".source = ./dotfiles/config/claude-personal/keybindings.json;
    ".config/claude-personal/output-styles/ELI5.md".source = ./claude-output-styles/ELI5.md;
    ".config/claude-gmatter/output-styles/ELI5.md".source = ./claude-output-styles/ELI5.md;
  };

  # Writable settings: seed defaults, preserve login/runtime/user-owned fields.
  # Never manage auth.json, .credentials.json, sessions, or global ~/.claude.json.
  home.activation.claudeProfileDefaults = lib.hm.dag.entryAfter ["writeBoundary"] ''
    for profile in claude-personal claude-gmatter; do
      dir="$HOME/.config/$profile"
      mkdir -p "$dir"
      if [ ! -f "$dir/settings.json" ]; then
        echo '{}' > "$dir/settings.json"
      fi
      tmp="$(${pkgs.coreutils}/bin/mktemp "$dir/settings.json.XXXXXX")"
      ${jq} --argjson defaults '${builtins.toJSON claudeDefaults}' \
        '$defaults * .' "$dir/settings.json" > "$tmp"
      if [ "$profile" = claude-gmatter ]; then
        ${jq} '.outputStyle //= "ELI5"' "$tmp" > "$tmp.work"
        mv "$tmp.work" "$tmp"
      fi
      chmod 0600 "$tmp"
      mv "$tmp" "$dir/settings.json"
    done
  '';
}
