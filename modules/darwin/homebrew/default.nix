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

    taps = [
      "FelixKratz/homebrew-formulae"
      "nikitabobko/homebrew-tap"
      "tabbyml/homebrew-tabby"
    ];

    brews = [
      "blueutil"
      "borders"
      # TODO: can we find a better/more nix way?
      "pyenv"
      "switchaudio-osx"
      "tabby"
      "trash"
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
      "lm-studio"
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
      "tailscale"
      "visual-studio-code"
    ];
  };
}
