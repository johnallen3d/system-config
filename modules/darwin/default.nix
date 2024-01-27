{...}: {
  system.stateVersion = 4;
  services.nix-daemon.enable = true;

  nix = {
    gc = {
      automatic = true;
      interval = {
        Weekday = 0;
        Hour = 0;
        Minute = 0;
      };
      options = "--delete-older-than 30d";
    };

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

  system.activationScripts.extraActivation.text = builtins.readFile ./activation.sh;
}
