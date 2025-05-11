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
      "common-fate/granted"
    ];

    brews = [
      "blueutil"
      "borders"
      "cloudflared"
      # "dagger"
      "datafusion"
      # "dotnet@6"
      "granted"
      # "libspatialite"
      # using this vs nix-package due to issues with SbarLua
      "lua"
      "pyenv" # TODO: can we find a better/more nix way?
      "switchaudio-osx"
      "tabiew" # TODO: prefer nix package when fixed
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
      "carbon-copy-cloner"
      "claude"
      "cleanshot"
      "cloudmounter"
      "discord"
      "disk-inventory-x"
      "docker"
      # "dotnet-sdk" # this is v8
      "ghostty"
      "istat-menus"
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
      # this is blowing up 🤷‍♂️
      # "stolendata-mpv"
      "syncthing"
      "tailscale"
      "tableplus"
      # "utm"
      "visual-studio-code"
      "whatsapp"
      "zed"
    ];
  };
}
