{config, ...}: let
  homebrewTrustJson = builtins.toJSON {
    trustedtaps = [
      "common-fate/granted"
      "dmno-dev/tap"
      "elio-fm/elio"
      "felixkratz/formulae"
      "kcl-lang/tap"
      "ksdme/tap"
      "nikitabobko/tap"
      "siderolabs/tap"
      "steipete/tap"
    ];
    trustedcasks = [
      "nikitabobko/tap/aerospace"
    ];
  };
in {
  system.activationScripts.preActivation.text = ''
        install -d -m 700 -o ${config.system.primaryUser} -g staff /Users/${config.system.primaryUser}/.homebrew
        cat > /Users/${config.system.primaryUser}/.homebrew/trust.json <<'EOF'
    ${homebrewTrustJson}
    EOF
        chown ${config.system.primaryUser}:staff /Users/${config.system.primaryUser}/.homebrew/trust.json
        chmod 600 /Users/${config.system.primaryUser}/.homebrew/trust.json
  '';

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
      "FelixKratz/homebrew-formulae"
      "common-fate/granted"
      "dmno-dev/tap"
      "elio-fm/elio"
      "kcl-lang/tap"
      "ksdme/tap"
      "nikitabobko/homebrew-tap"
      "siderolabs/tap"
      "steipete/tap"
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
      "kcl-lsp"
      # "libspatialite"
      # using this vs nix-package due to issues with SbarLua
      "lua"
      "mise"
      "rtk"
      "sheets"
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
      "codex-app"
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
