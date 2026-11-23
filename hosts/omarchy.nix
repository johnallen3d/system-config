# Omarchy: the primary Arch host. It alone runs the singleton services.
{
  config,
  pkgs,
  ...
}: {
  imports = [
    ./omarchy-common.nix
    ../modules/home-manager/antigravity.nix
    ../modules/home-manager/tuicr.nix
    ../modules/home-manager/omarchy-credits.nix
    ../modules/home-manager/omarchy-nod.nix
    ../modules/home-manager/omarchy-syncthing-lan.nix
  ];

  services.rex.tailscale.hostname = "rex-omarchy";

  # Tailscale-only VNC listener (this node's stable tailnet IP).
  omarchyVnc.address = "100.97.112.40";

  # Central gateway for every other host's clients.
  subscriptionProxy.server.enable = true;

  # Personal-only agy (no profiles), routed through the personal proxy.
  antigravity.enable = true;
  nixpkgs.config.allowUnfreePackages = ["antigravity-cli"];

  # The Syncthing-paired Obsidian vault is local to Omarchy.
  home.sessionVariables.PI_SESSION_CAPTURE_VAULT_PATH = "${config.home.homeDirectory}/notes";
  # The notes repo's mise tasks read and write that vault through vlt, and
  # reach Gmail and Calendar through gog.
  home.packages = [
    (import ../modules/home-manager/packages/vlt.nix {inherit pkgs;})
    pkgs.gogcli
  ];
}
