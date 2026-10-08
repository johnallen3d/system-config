{
  config,
  lib,
  pkgs,
  ...
}: let
  common = import ../common/common.nix {inherit pkgs;};
in {
  imports = [
    ./fish
    ./packages/omarchy-fish.nix
    ./starship
  ];

  programs.fish = {
    shellAliases = common.shellAliases;
    shellInit = ''
      set -gx SHELL ${lib.getExe pkgs.fish}
    '';
  };

  # Leave Omarchy's Bash prompt and ~/.config/starship.toml untouched.
  programs.starship = {
    configPath = "${config.xdg.configHome}/fish/starship.toml";
    enableBashIntegration = false;
    enableZshIntegration = false;
  };

  # Use Omarchy's native mise and Neovim; do not replace their configuration.
  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    GIT_EDITOR = "nvim";
    PI_RESPONSE_FEEDBACK = "1";
    TIME_STYLE = "long-iso";
  };

  xdg.configFile = {
    "television/config.toml".source = ./dotfiles/config/television/config.toml;
    "television/cable/fish-history.toml".source = ./dotfiles/config/television/cable/fish-history.toml;
  };
}
