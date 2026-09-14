{
  config,
  lib,
  pkgs,
  ...
}: let
  herdr = "${pkgs.herdr}/bin/herdr";
  homeDir = config.home.homeDirectory;
in {
  # Herdr resolves integrations from the active agent profile environment.
  # Install into both personal/work Pi and Claude profile pairs after their
  # mutable settings files have been initialized.
  home.activation.herdrIntegrations = lib.hm.dag.entryAfter ["piSettings" "piWorkSettings"] ''
    for profile in "${homeDir}/.config/pi" "${homeDir}/.config/pi-work"; do
      PI_CODING_AGENT_DIR="$profile" ${herdr} integration install pi
    done

    for profile in "${homeDir}/.config/claude-personal" "${homeDir}/.config/claude-gmatter"; do
      CLAUDE_CONFIG_DIR="$profile" ${herdr} integration install claude
    done
  '';
}
