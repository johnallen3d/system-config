{
  pkgs,
  lib,
  ...
}: let
  managedTheme = import ../managed-theme.nix {inherit lib;};
in {
  programs.fish = {
    enable = true;

    interactiveShellInit = builtins.replaceStrings ["tokyo-night-moon"] [managedTheme.activeTheme.hyphenName] (builtins.readFile ./config.fish);

    plugins = [
      {
        name = "done";
        src = pkgs.fishPlugins.done.src;
      }
      {
        name = "colored-man-pages";
        src = pkgs.fishPlugins.colored-man-pages.src;
      }
    ];
  };

  # https://github.com/vitallium/tokyonight-fish
  # https://github.com/nix-community/home-manager/issues/3724#issue-1604681266
  home.file = lib.mapAttrs' (variant: theme:
    lib.nameValuePair ".config/fish/themes/${managedTheme.hyphenThemeName variant}.theme" {text = theme;}) managedTheme.fishThemes;

  imports = [
    ./functions.nix
  ];
}
