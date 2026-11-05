# Omarchy: the primary Arch host. It alone runs the singleton services.
{config, ...}: {
  imports = [
    ./omarchy-common.nix
    ../modules/home-manager/omarchy-credits.nix
    ../modules/home-manager/omarchy-pi-pocket.nix
    ../modules/home-manager/omarchy-syncthing-lan.nix
  ];

  services.rex.tailscale.hostname = "rex-omarchy";

  # John's production assistant (Pi Pocket / Pi Durable); replaced Hermes.
  piPocket.enable = true;

  # Central gateway for every other host's clients.
  subscriptionProxy.server.enable = true;

  # The Syncthing-paired Obsidian vault is local to Omarchy.
  home.sessionVariables.PI_SESSION_CAPTURE_VAULT_PATH = "${config.home.homeDirectory}/notes";
}
