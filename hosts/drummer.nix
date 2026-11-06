# Drummer: 2013 Mac Pro running Omarchy. Mirrors Miller: Omarchy without its
# singletons (Pi Pocket, subscription proxy server, credits, Syncthing LAN forwarder).
{...}: {
  imports = [./omarchy-common.nix];

  services.rex.tailscale.hostname = "rex-drummer";

  # Tailscale-only VNC listener (this node's stable tailnet IP).
  omarchyVnc.address = "100.78.246.113";
}
