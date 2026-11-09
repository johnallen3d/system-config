# Switchyard's Rex actions (./switchyard/lua/switchyard: the tab picker, the
# new float and the float helpers), linked to ~/.config/rex/switchyard where
# the Rex init.lua requires them. Mac-only, like the rest of the Rex config;
# the binaries the floats run come from ./switchyard.nix on every host.
{
  lib,
  pkgs,
  ...
}: {
  config = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
    xdg.configFile."rex/switchyard".source = ./switchyard/lua/switchyard;
  };
}
