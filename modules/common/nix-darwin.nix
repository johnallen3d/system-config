{
  pkgs,
  user,
  home,
  ...
}: let
  common = import ./common.nix {inherit pkgs;};
in {
  environment.shells = common.commonShells;
  environment.variables = common.commonVariables;
  environment.shellAliases = common.shellAliases;

  programs.fish.enable = true;

  users.users.${user} = {
    home = "${home}";
    shell = pkgs.fish;
  };
}
