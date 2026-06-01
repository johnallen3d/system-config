{
  lib,
  pkgs,
  user ? null,
  home ? null,
  ...
}: let
  common = import ./common.nix {inherit pkgs;};
in {
  environment.shells = common.commonShells;
  environment.variables = common.commonVariables;
  environment.shellAliases = common.shellAliases;

  programs.fish.enable = true;

  users.users = lib.mkIf (user != null) {
    ${user} = {
      home = lib.mkIf (home != null) home;
      shell = pkgs.fish;
    };
  };
}
