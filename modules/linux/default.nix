{pkgs, ...}: {
  system.stateVersion = "23.11";

  nix = {
    optimise.automatic = true;
    gc = {
      automatic = true;
      dates = "weekly";
      options = "--delete-older-than 30d";
    };

    settings = {
      cores = 0; # max
      max-jobs = 10;
      experimental-features = [
        "nix-command"
        "flakes"
      ];
    };
  };

  imports = [
    /etc/nixos/hardware-configuration.nix
  ];

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "drummer";
  networking.networkmanager.enable = true;

  time.timeZone = "America/New_York";

  fonts = {
    fontconfig = {
      antialias = true;
      hinting = {
        enable = true;
        autohint = true;
      };
    };
  };

  # Select internationalisation properties.
  i18n.defaultLocale = "en_US.UTF-8";

  services.xserver = {
    enable = true;

    dpi = 180;

    libinput.touchpad.naturalScrolling = true;

    desktopManager = {
      xterm.enable = true;

      xfce = {
        enable = true;
        noDesktop = true;
        enableXfwm = false;
      };
    };

    displayManager = {
      defaultSession = "xfce+i3";
      sessionCommands = ''
        ${pkgs.xorg.xrandr}/bin/xrandr - '2048x1152'
      '';
    };

    windowManager.i3 = {
      enable = true;
      extraPackages = with pkgs; [
        dmenu
        i3status
        i3lock
        i3blocks
      ];
    };
  };

  # Configure keymap in X11
  services.xserver.xkb.layout = "us";
  # services.xserver.xkb.options = "eurosign:e,caps:escape";

  # Enable touchpad support (enabled default in most desktopManager).
  services.xserver.libinput.enable = true;

  users.users."john.allen" = {
    isNormalUser = true;
    extraGroups = ["wheel"]; # Enable ‘sudo’ for the user.
  };

  fonts = {
    # paid fonts (eg. Font Awesome Pro) installed at "modules/home-manager/default.nix"
    fontDir.enable = true;

    packages = with pkgs; [
      cascadia-code
      monaspace
      (nerdfonts.override {fonts = ["CascadiaCode" "Hack"];})
    ];
  };

  # TODO: this isn't working but is what's documented
  # https://nixos.wiki/wiki/1Password
  programs._1password.enable = true;
  programs._1password-gui = {
    enable = true;
    # Certain features, including CLI integration and system authentication support,
    # require enabling PolKit integration on some desktop environments (e.g. Plasma).
    # polkitPolicyOwners = ["yourUsernameHere"];
  };
}
