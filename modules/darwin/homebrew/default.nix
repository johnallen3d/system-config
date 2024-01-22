{...}: {
  homebrew = {
    enable = true;
    caskArgs.no_quarantine = true;
    onActivation = {autoUpdate = true;};
    global.brewfile = true;

    brews = [
      "blueutil"
      "borders"
    ];

    taps = [];

    casks = [
      "1password"
      "1password-cli"
      "aerial"
      "aerospace"
      "arc"
      "brave-browser"
      "cleanshot"
      "discord"
      "disk-inventory-x"
      "docker"
      "dropbox"
      "grammarly-desktop"
      "istat-menus"
      "karabiner-elements"
      "kitty"
      "lunar"
      "marked"
      "mpv"
      "notunes"
      "obsidian"
      "ollama"
      "opera"
      "rambox"
      "raycast"
      "rocket"
      "visual-studio-code"
    ];

    # TODO:
    # Cody
    # WireGuard

    masApps = {
      "1Password for Safari" = 1569813296;
      "Balance Lock" = 1019371109;
      "CARROT Weather" = 993487541;
      "Key Codes" = 414568915;
      "Pixelmator Pro" = 1289583905;
      "Slack" = 803453959;
      "WireGuard" = 1451685025;
      # "Xcode" = 497799835;
    };
  };
}
