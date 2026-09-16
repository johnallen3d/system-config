{
  pkgs,
  lib,
  ...
}: let
  managedTheme = import ../managed-theme.nix {inherit lib;};
  worktrunkFishIntegration = pkgs.runCommand "worktrunk-fish-integration-${pkgs.worktrunk.version}" {} ''
    mkdir -p "$out/functions" "$out/completions"
    ${pkgs.worktrunk}/bin/wt config shell init fish > "$out/functions/wt.fish"
    ${pkgs.worktrunk}/bin/wt config shell completions fish > "$out/completions/wt.fish"
  '';
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
  home.file =
    lib.mapAttrs' (variant: theme:
      lib.nameValuePair ".config/fish/themes/${managedTheme.hyphenThemeName variant}.theme" {text = theme;})
    managedTheme.fishThemes
    // {
      ".config/fish/completions/wt.fish".source = "${worktrunkFishIntegration}/completions/wt.fish";
      ".config/fish/functions/wt.fish".source = "${worktrunkFishIntegration}/functions/wt.fish";
    };

  imports = [
    ./functions.nix
  ];
}
