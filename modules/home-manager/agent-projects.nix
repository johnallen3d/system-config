{
  config,
  lib,
  pkgs,
  ...
}: let
  amfaroConfig = "${config.home.homeDirectory}/dev/src/amfaro/mise.toml";
  delegationInstructions = builtins.readFile ./agent-projects/delegation-instructions.md;
  omarchyInstructions = lib.optionalString pkgs.stdenv.hostPlatform.isLinux ''

    ## Arch/Omarchy

    This is standalone Home Manager on Arch/Omarchy, not macOS or NixOS.
    Never run macOS rebuild tasks here or change Omarchy shell/desktop settings.
    See docs/omarchy-agents.md in system-config for application and authentication.
  '';
  personalInstructions =
    ''
      # Personal agent instructions

      - Always respond in English. The user's name is John Allen.
      - Respect `PI_CODING_AGENT_DIR` and `CLAUDE_CONFIG_DIR`; keep profiles,
        credentials, and sessions separate.

    ''
    + delegationInstructions
    + omarchyInstructions;
  workInstructions =
    builtins.readFile ./agent-projects/work-instructions.md
    + "\n"
    + delegationInstructions
    + omarchyInstructions;
in {
  imports = [./claude-work-context.nix];

  # Shared directory context, not project dependencies (those stay in mise).
  # Home Manager must fail on unexpected unmanaged files; review/back up before
  # adopting an existing config rather than forcing replacement.
  home.file = {
    "dev/src/amfaro/mise.toml".source = ./agent-projects/amfaro-mise.toml;
    # Global instructions follow the selected profile even outside the parent tree.
    ".config/pi/AGENTS.md".text = personalInstructions;
    ".config/claude-personal/CLAUDE.md".text = personalInstructions;
    ".config/pi-work/AGENTS.md".text = workInstructions;
    ".config/claude-gmatter/CLAUDE.md".text = workInstructions;
  };

  # Trust only this managed config, after the new generation's link is installed.
  # Use a pinned CLI for activation, without replacing either host's native mise.
  home.activation.trustAgentProjects = lib.hm.dag.entryAfter ["linkGeneration"] ''
    $DRY_RUN_CMD ${lib.getExe pkgs.mise} trust ${lib.escapeShellArg amfaroConfig}
  '';
}
