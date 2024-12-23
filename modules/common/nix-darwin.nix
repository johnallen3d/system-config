{
  config,
  lib,
  pkgs,
  ...
}: let
  common = import ./common.nix {inherit pkgs;};
in {
  environment.shells = common.commonShells;
  environment.variables = common.commonVariables;
  environment.shellAliases = common.shellAliases;

  users.users.${config.user} = lib.mkIf (config ? user) {
    home = lib.mkIf (config ? home) config.home;
    shell = pkgs.fish;
  };
}
