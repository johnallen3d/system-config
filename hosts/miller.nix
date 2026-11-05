# Miller: 2013 Mac Pro running Omarchy. Mirrors Omarchy without its singletons
# (Pi Pocket, subscription proxy server, credits, Syncthing LAN forwarder).
{...}: {
  imports = [./omarchy-common.nix];

  services.rex.tailscale.hostname = "rex-miller";
}
