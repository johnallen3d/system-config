{pkgs, ...}: {
  system.stateVersion = 4;
  ids.gids.nixbld = 350;

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

      trusted-users = [
        "root"
        "john.allen"
      ];
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

  fonts = {
    packages = with pkgs; [
      cascadia-code
      fira-code
      jetbrains-mono
      monaspace
      nerd-fonts.caskaydia-cove
      nerd-fonts.fira-code
      nerd-fonts.hack
      nerd-fonts.jetbrains-mono
    ];
  };
}
