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
      "common-fate/granted"
      "dmno-dev/tap"
      "kcl-lang/tap"
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
      "duckdb"
      "granted"
      "kcl-lsp"
      # "libspatialite"
      # using this vs nix-package due to issues with SbarLua
      "lua"
      "switchaudio-osx"
      "tabiew" # TODO: prefer nix package when fixed
      # "talosctl"
      "trash"
      "varlock"
    ];

    casks = [
      "1password"
      "1password-cli"
      "aerial"
      "aerospace"
      "arc"
      "betterdisplay"
      "brave-browser"
      "carbon-copy-cloner"
      "claude"
      "cleanshot"
      "cloudmounter"
      "discord"
      "disk-inventory-x"
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
