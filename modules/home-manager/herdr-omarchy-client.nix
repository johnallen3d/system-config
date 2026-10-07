{
  lib,
  pkgs,
  ...
}: let
  setup = import ./packages/bin/herdr-omarchy-setup.nix {inherit pkgs;};
in {
  home.packages = [setup];

  # Seed through the supported CLI rather than managing Herdr's mutable machine
  # catalog/selection/cache. An offline box must not break a Mac rebuild.
  home.activation.herdrOmarchyMachine = lib.hm.dag.entryAfter ["writeBoundary"] ''
    if ! $DRY_RUN_CMD ${setup}/bin/herdr-omarchy-setup; then
      echo 'Omarchy registration deferred; run herdr-omarchy-setup when SSH/server access is ready.' >&2
    fi
  '';
}
