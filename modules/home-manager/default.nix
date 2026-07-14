{
  lib,
  pkgs,
  ...
}: let
  common = import ../common/common.nix {inherit pkgs;};
  musicDir = common.commonVariables.MUSIC_DIR;
  managedTheme = import ./managed-theme.nix {inherit lib;};
  solidWallpaper = pkgs.runCommand "solid-wallpaper.png" {
    nativeBuildInputs = [pkgs.imagemagick];
  } ''
    magick -size 1x1 "xc:${managedTheme.activeTheme.palette.wallpaper or managedTheme.activeTheme.palette.bg}" PNG32:"$out"
  '';
  configDir = pkgs.runCommand "home-config-dir" {} ''
    cp -R ${./dotfiles/config} "$out"
    chmod -R u+w "$out"
    mkdir -p "$out/bat/themes" "$out/ghostty/themes"
${lib.concatMapStringsSep "\n" (variant: ''    cat > "$out/bat/themes/${managedTheme.batThemeName variant}.tmTheme" <<'EOF'
${managedTheme.batThemes.${variant}}
EOF'') managedTheme.variantNames}
${lib.concatMapStringsSep "\n" (variant: ''    cat > "$out/ghostty/themes/${managedTheme.hyphenThemeName variant}" <<'EOF'
${managedTheme.ghosttyThemes.${variant}}
EOF'') managedTheme.variantNames}
    substituteInPlace "$out/ghostty/config" \
      --replace-fail "theme = tokyo-night-moon" "theme = ${managedTheme.activeTheme.hyphenName}"
    substituteInPlace "$out/borders/bordersrc" \
      --replace-fail "__BORDERS_ACTIVE_COLOR__" "${managedTheme.activeBordersActiveColor}" \
      --replace-fail "__BORDERS_ACTIVE_ACCENT__" "${managedTheme.activeBordersActiveAccent}"
    substituteInPlace "$out/sketchybar/sketchybarrc.sh" \
      --replace-fail 'source "$HOME/.local/share/theme/tokyo-night-sketchybar.sh"' 'source "$HOME/.local/share/theme/${managedTheme.activeTheme.hyphenName}-sketchybar.sh"'
    cat > "$out/sketchybar/colors.lua" <<'EOF'
${managedTheme.sketchybarColorsLua}
EOF
  '';
in {
  home.stateVersion = "24.05";

  imports = [
    ./packages
    ./claude-prompts.nix
    ./obsidian.nix
    ./pi-extensions.nix
    ./pi-prompts.nix
    ./pi-settings.nix
  ];

  home.sessionVariables = {
    CLAUDE_CONFIG_DIR = "$HOME/.config/claude-personal";
    CLAUDE_CODE_DISABLE_1M_CONTEXT = "1";
    CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1";
  };

  programs.desktoppr = lib.mkIf pkgs.stdenv.isDarwin {
    enable = true;
    settings = {
      picture = "${solidWallpaper}";
      color = lib.removePrefix "#" (managedTheme.activeTheme.palette.wallpaper or managedTheme.activeTheme.palette.bg);
      scale = "fill";
    };
  };

  home = {
    activation.claudeCodeSymlink = lib.hm.dag.entryAfter ["writeBoundary"] ''
      if [ -x /opt/homebrew/bin/claude ]; then
        mkdir -p "$HOME/.local/bin"
        ln -snf /opt/homebrew/bin/claude "$HOME/.local/bin/claude"
      fi
    '';

    # Telegram only supports a partial managed-theme flow.
    # We write a regular file at a stable HOME path so Telegram can keep pointing
    # at it after the user selects it once via Settings -> Chat Settings ->
    # Chat Wallpaper -> Choose from file. Avoid a store symlink here because
    # Telegram may remember the chosen absolute file path across launches.
    activation.telegramManagedTheme = lib.hm.dag.entryAfter ["writeBoundary"] ''
      mkdir -p "$HOME/.local/share/theme"
      cat > "$HOME/.local/share/theme/telegram-managed.tdesktop-theme" <<'EOF'
${managedTheme.telegramTheme}
EOF
      chmod 0644 "$HOME/.local/share/theme/telegram-managed.tdesktop-theme"
    '';

    file = {
      ".ctags".source = ./dotfiles/ctags;
      ".irbrc".source = ./dotfiles/irbrc;
      ".pryrc".source = ./dotfiles/pryrc;
      ".sqliterc".source = ./dotfiles/sqliterc;

      ".config/gh-dash/config.yml".source = ./dotfiles/config/gh-dash/config.yml;
      ".config/stylua.toml".source = ./dotfiles/config/stylua.toml;
      ".config/claude-gmatter/keybindings.json".source = ./dotfiles/config/claude-personal/keybindings.json;
      "Library/Application Support/elio/config.toml".text = ''
        [ui]
        show_top_bar = false
      '';

      "Library/Application Support/elio/theme.toml".source = (pkgs.formats.toml {}).generate "elio-theme.toml" managedTheme.elioTheme;

      ".local/share/theme/${managedTheme.activeTheme.hyphenName}-sketchybar.sh".text = managedTheme.sketchybarThemeSh;

      ".config" = {
        recursive = true;
        source = configDir;
      };

      "bin" = {
        recursive = true;
        source = ./dotfiles/bin;
      };

      ".tabby-client/agent/config.toml".source = ./dotfiles/tabby.toml;

      "Library/Application Support/org.dystroy.bacon/prefs.toml".source = ./dotfiles/bacon-prefs.toml;

      ".config/yem/config.toml".text = ''
        # yem configuration

        music_directory = "${musicDir}"

        [favorites]
        caamp = "Caamp/Lavender Days"
        caleb = "Caleb Grenier/Sandy Friends"
        dave = "Dave Matthews & Tim Reynolds/Live At Luther College"
        gizz = "King Gizzard & The Lizard Wizard/Nonagon Infinity"
        gogo = "GoGo Penguin/Man Made Object"
        goose = "Goose/Alive and Well"
        hania = "Hania Rani/Ghosts"
        joseph = "JOSEPH/I'm Alone, No You're Not"
        khruangbin = "Khruangbin/A LA SALA"
        nin = "Nine Inch Nails/Live at PNC Music Pavilion, Charlotte, NC (2014-08-07)"
        noah = "Noah Kahan/Cape Elizabeth"
        ray = "Ray LaMontagne/Ouroboros"
        sarah = "Sarah Jarosz/Blue Heron Suite"
        tool = "Tool/Undertow"
        trey = "Trey Anastasio/Lonely Trip"
        violent = "Violent Femmes/Violent Femmes"
      '';
    } // lib.optionalAttrs pkgs.stdenv.isDarwin {};
  };
}
