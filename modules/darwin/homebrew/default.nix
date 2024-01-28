{...}: {
  homebrew = {
    enable = true;
    caskArgs.no_quarantine = true;
    onActivation = {
      autoUpdate = true;
      cleanup = "zap";
      upgrade = true;
    };
    global.brewfile = true;

    brews = [
      "blueutil"
      "borders"
      "switchaudio-osx"
    ];

    taps = [
      "FelixKratz/homebrew-formulae"
      "nikitabobko/homebrew-tap"
    ];

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
  };
}
