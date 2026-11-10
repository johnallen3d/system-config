{pkgs, ...}: {
  system.stateVersion = 4;
  ids.gids.nixbld = 350;

  # nix-darwin docs can lag nixpkgs' nixos-render-docs CLI on unstable.
  documentation.enable = false;
  system.tools.darwin-uninstaller.enable = false;

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

      auto-optimise-store = true;

      trusted-users = [
        "root"
        "john.allen"
      ];

      extra-substituters = [
        "https://johnallen3d.cachix.org"
        "https://nix-community.cachix.org"
      ];
      extra-trusted-public-keys = [
        "johnallen3d.cachix.org-1:E4yp86sK2e9gDTQ998xFR8NWFU+YhKMGIBAy0e+EjeM="
        "nix-community.cachix.org-1:mB9FSh9qf2dCimDSUage0tHzD5IbNoKnQ3p2anhjLmQ="
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
}
