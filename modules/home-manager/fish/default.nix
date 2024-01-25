{...}: {
  programs.fish = {
    enable = true;

    interactiveShellInit = builtins.readFile ./config.fish;
  };

  imports = [
    ./functions.nix
    ./path_fix.nix
  ];
}
