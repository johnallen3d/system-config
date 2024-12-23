{pkgs, ...}: let
  common = import ./common.nix {inherit pkgs;};
in {
  home = {
    packages = common.commonShells;
    sessionVariables = common.commonVariables;
  };

  programs.fish.shellAliases = common.shellAliases;
}
