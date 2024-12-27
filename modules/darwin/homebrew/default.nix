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
      "siderolabs/tap"
    ];

    brews = [
      "blueutil"
      "borders"
      "cloudflared"
      # "dagger"
      "datafusion"
      # "dotnet@6"
      # "libspatialite"
      "pyenv" # TODO: can we find a better/more nix way?
      "switchaudio-osx"
      # "talosctl"
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
      # "dotnet-sdk" # this is v8
      "dropbox"
      "istat-menus"
      "jordanbaird-ice"
      "karabiner-elements"
      # "lunar"
      "marked"
      # issues with macOS Sequoia
      # https://github.com/canonical/multipass/issues/3661#issuecomment-2363403467
      # "multipass"
      "notunes"
      "obsidian"
      "ollama"
      "opera"
      "orbstack"
      "raycast"
      "rocket"
      "stolendata-mpv"
      "syncthing"
      "tailscale"
      # "utm"
      "visual-studio-code"
      "whatsapp"
    ];
  };
}
