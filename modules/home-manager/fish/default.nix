{pkgs, ...}: {
  programs.fish = {
    enable = true;

    interactiveShellInit = builtins.readFile ./config.fish;

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
  home.file.".config/fish/themes/tokyo-night-moon.theme".source = ./tokyo-night-moon.theme;

  imports = [
    ./functions.nix
    ./path_fix.nix
  ];
}
