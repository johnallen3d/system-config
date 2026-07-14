{...}: {
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      cleanup = "zap";
      # Homebrew now requires explicit confirmation for bundle cleanup.
      # Preserve existing managed cleanup behavior during nix-darwin activation.
      extraFlags = ["--force-cleanup"];
      upgrade = true;
    };
    global.brewfile = true;

    taps = [
      {
        name = "FelixKratz/homebrew-formulae";
        trusted = true;
      }
      {
        name = "common-fate/granted";
        trusted = true;
      }
      {
        name = "dmno-dev/tap";
        trusted = true;
      }
      {
        name = "elio-fm/elio";
        trusted = true;
      }
      {
        name = "kcl-lang/tap";
        trusted = true;
      }
      {
        name = "ksdme/tap";
        trusted = true;
      }
      {
        name = "nikitabobko/homebrew-tap";
        trusted = true;
      }
      {
        name = "siderolabs/tap";
        trusted = true;
      }
      {
        name = "steipete/tap";
        trusted = true;
      }
    ];

    brews = [
      "beads"
      "borders"
      "cloudflared"
      # "dagger"
      "datafusion"
      # "dotnet@6"
      "duckdb"
      "elio-fm/elio/elio"
      "gogcli"
      "hunk"
      "kcl-lsp"
      # "libspatialite"
      # using this vs nix-package due to issues with SbarLua
      "lua"
      "mise"
      "rtk"
      "sheets"
      "sketchybar"
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
      "aerospace"
      "arc"
      "betterdisplay"
      "brave-browser"
      "carbon-copy-cloner"
      "claude"
      # TODO: this is quite out of date
      # "claude-code"
      "cleanshot"
      "cloudmounter"
      "codex"
      "discord"
      "disk-inventory-x"
      # "dotnet-sdk" # this is v8
      "font-cascadia-code-pl"
      "font-caskaydia-cove-nerd-font"
      "font-fira-code"
      "font-fira-code-nerd-font"
      "font-hack-nerd-font"
      "font-jetbrains-mono"
      "font-jetbrains-mono-nerd-font"
      "font-monaspace"
      "fluidvoice"
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
      # "ollama-app"
      "orbstack"
      "raycast"
      "rocket"
      "signal"
      # this is blowing up 🤷‍♂️
      "stolendata-mpv"
      "supacode"
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
