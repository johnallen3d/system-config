{...}: {
  system.stateVersion = 4;
  services.nix-daemon.enable = true;

  nix = {
    settings = {
      cores = 0; # max
      max-jobs = 10;
    };

    extraOptions = ''
      experimental-features = nix-command flakes
    '';
  };

  imports = [
    ./agents
    ./homebrew
    ./system
    ./environment
  ];
}
