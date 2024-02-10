{pkgs, ...}: {
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

  fonts = {
    # paid fonts (eg. Font Awesome Pro) installed at "modules/home-manager/default.nix"
    fontDir.enable = true;

    fonts = with pkgs; [
      cascadia-code
      monaspace
      (nerdfonts.override {fonts = ["CascadiaCode" "Hack"];})
    ];
  };
}
