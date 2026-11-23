# Miller: 2013 Mac Pro running Omarchy. Mirrors Omarchy without its singletons
# (subscription proxy server, credits, Syncthing LAN forwarder).
{...}: {
  imports = [
    ./omarchy-common.nix
    ../modules/home-manager/omarchy-vnc.nix
    ../modules/home-manager/omarchy-voxl.nix
    ../modules/home-manager/tuicr.nix
  ];

  services.rex.tailscale.hostname = "rex-miller";

  # Tailscale-only VNC listener (this node's stable tailnet IP).
  omarchyVnc.address = "100.113.199.114";

  # Headless browser desktop with the shared agent browser, beside WayVNC.
  omarchyVoxl.host = "miller.taila14c2.ts.net";
}
