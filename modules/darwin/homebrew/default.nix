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
      "ksdme/tap"
      "nikitabobko/homebrew-tap"
      "plutov/tap"
      "siderolabs/tap"
      "steveyegge/beads"
      # opencode, see note below
      # "sst/tap"
    ];

    brews = [
      "bd"
      "blueutil"
      "borders"
      "cloudflared"
      # "dagger"
      "datafusion"
      "dbmate"
      # "dotnet@6"
      "duckdb"
      "granted"
      "kcl-lsp"
      # "libspatialite"
      # using this vs nix-package due to issues with SbarLua
      "lua"
      "llm" # broken in nixpkgs jan 2025
      "mole"
      # not being kept up to date with raprid releases
      # trying: curl -fsSL https://opencode.ai/install | bash
      # with autoupdate enabled
      # "opencode"
      "sqruff"
      # "switchaudio-osx"
      # TODO: prefer nix package when fixed
      "tabiew" # 👇 tui for parquet
      # "talosctl"
      "trash"
      "ut"
    ];

    casks = [
      "1password"
      "1password-cli"
      "aerial"
      "aerospace"
      "arc"
      "betterdisplay"
      "brave-browser"
      "bruno"
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
      # "kindavim"
      # "lunar"
      "marked-app"
      # issues with macOS Sequoia
      # https://github.com/canonical/multipass/issues/3661#issuecomment-2363403467
      # "multipass"
      "notunes"
      "obsidian"
      "ollama-app"
      "opera"
      "oq" # TUI for reading openapi specs
      "orbstack"
      "raycast"
      "rocket"
      # this is blowing up 🤷‍♂️
      "stolendata-mpv"
      "syncthing-app"
      "tailscale-app"
      "tableplus"
      "telegram-desktop"
      # "utm"
      "visual-studio-code"
      "whatsapp"
      # "wooshy"
      "zed"
      "zen"
    ];
  };
}
