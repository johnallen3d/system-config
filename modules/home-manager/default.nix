{
  config,
  lib,
  pkgs,
  ...
}: let
  common = import ../common/common.nix {inherit pkgs;};
  musicDir = common.commonVariables.MUSIC_DIR;
  managedTheme = import ./managed-theme.nix {inherit lib;};
  llmUsage = import ./packages/llm-usage.nix {inherit pkgs;};
  llmUsageJson = "${config.xdg.cacheHome}/llm-usage/usage.json";
  llmUsageState = "${config.home.homeDirectory}/.local/state/llm-usage";
  llmUsagePersonalJson = "${config.xdg.cacheHome}/llm-usage/personal.json";
  llmUsageAgent = pkgs.writeShellApplication {
    name = "llm-usage-agent";
    text = ''
      umask 077
      if ! key=$(/usr/bin/security find-generic-password \
        -s llm-usage-cliproxy-work -a ${lib.escapeShellArg config.home.username} -w); then
        echo "llm-usage-agent: cannot read Keychain item llm-usage-cliproxy-work" >&2
        exit 1
      fi
      export LLM_USAGE_CLIPROXY_MANAGEMENT_KEY="$key"
      exec ${llmUsage}/bin/llm-usage json --source cliproxy --interval 60 \
        --output ${lib.escapeShellArg llmUsageJson}
    '';
  };
  llmUsagePersonalAgent = pkgs.writeShellApplication {
    name = "llm-usage-personal-agent";
    text = ''
      umask 077
      # Personal collection never inherits work endpoint/account selectors.
      unset LLM_USAGE_CLIPROXY_URL LLM_USAGE_CLIPROXY_MANAGEMENT_KEY
      unset LLM_USAGE_CLIPROXY_CODEX_AUTH_INDEX WORK_LLM_USAGE_CLIPROXY_CODEX_AUTH_INDEX
      unset LLM_USAGE_CLIPROXY_CLAUDE_AUTH_INDEX WORK_LLM_USAGE_CLIPROXY_CLAUDE_AUTH_INDEX
      unset LLM_USAGE_CLIPROXY_CODEX_ACCOUNT_ID WORK_LLM_USAGE_CLIPROXY_CODEX_ACCOUNT_ID
      # The child expands the URL only after the two selected Doppler settings
      # are injected. The management key stays in the child's environment.
      # shellcheck disable=SC2016
      exec ${lib.getExe pkgs.doppler} run --no-read-env --no-check-version \
        --project system-config --config dev_personal --no-fallback \
        --only-secrets PERSONAL_LLM_USAGE_CLIPROXY_URL,PERSONAL_LLM_USAGE_CLIPROXY_MANAGEMENT_KEY -- \
        ${pkgs.bash}/bin/bash -eu -c '
          exec "$@" --cliproxy-url "$PERSONAL_LLM_USAGE_CLIPROXY_URL"
        ' -- ${llmUsage}/bin/llm-usage json --source cliproxy \
        --provider claude-code --provider codex \
        --cliproxy-key-env PERSONAL_LLM_USAGE_CLIPROXY_MANAGEMENT_KEY --interval 60 \
        --output ${lib.escapeShellArg llmUsagePersonalJson}
    '';
  };
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
    substituteInPlace "$out/sketchybar/plugins/llm-usage.sh" \
      --replace-fail '@usageJson@' '${llmUsageJson}'
    cat > "$out/sketchybar/colors.lua" <<'EOF'
${managedTheme.sketchybarColorsLua}
EOF
  '';
in {
  home.stateVersion = "24.05";

  imports = [
    ./packages
    ./agent-projects.nix
    ./claude-prompts.nix
    ./doppler.nix
    ./obsidian.nix
    ./pi-extensions.nix
    ./pi-prompts.nix
    ./pi-settings.nix
    ./subscription-proxy.nix
  ];

  subscriptionProxy.enable = pkgs.stdenv.hostPlatform.isDarwin;

  home.activation.llmUsageState = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin
    (lib.hm.dag.entryAfter ["writeBoundary"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        ${pkgs.coreutils}/bin/install -d -m 0700 \
          ${lib.escapeShellArg llmUsageState} \
          ${lib.escapeShellArg (builtins.dirOf llmUsageJson)}
        # launchd opens its log files before applying the job's umask.
        ${pkgs.coreutils}/bin/touch \
          ${lib.escapeShellArg "${llmUsageState}/agent.log"} \
          ${lib.escapeShellArg "${llmUsageState}/agent.err.log"} \
          ${lib.escapeShellArg "${llmUsageState}/personal.log"} \
          ${lib.escapeShellArg "${llmUsageState}/personal.err.log"}
        ${pkgs.coreutils}/bin/chmod 0600 \
          ${lib.escapeShellArg "${llmUsageState}/agent.log"} \
          ${lib.escapeShellArg "${llmUsageState}/agent.err.log"} \
          ${lib.escapeShellArg "${llmUsageState}/personal.log"} \
          ${lib.escapeShellArg "${llmUsageState}/personal.err.log"}
      fi
    '');

  # A running Rex server keeps the config it loaded; reread the managed
  # ~/.config/rex (Mac-only, below). Exit 4 means no server is running.
  home.activation.rexConfigReload = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin
    (lib.hm.dag.entryAfter ["linkGeneration"] ''
      rex=${lib.escapeShellArg "${config.home.homeDirectory}/.local/bin/rex"}
      if [ -z "''${DRY_RUN:-}" ] && [ -x "$rex" ]; then
        status=0
        out=$(env -u REX_SERVER "$rex" --autostart=false --timeout 5s config reload 2>&1) || status=$?
        if [ "$status" -ne 0 ] && [ "$status" -ne 4 ]; then
          echo "warning: rex config reload failed (exit $status); press shift+cmd+r in Rex" >&2
          printf '%s\n' "$out" >&2
        fi
      fi
    '');

  launchd.agents.llm-usage = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
    enable = true;
    config = {
      Label = "org.nix-community.home.llm-usage";
      ProgramArguments = ["${llmUsageAgent}/bin/llm-usage-agent"];
      EnvironmentVariables.LLM_USAGE_CLIPROXY_URL = "http://${config.subscriptionProxy.address}:8318";
      RunAtLoad = true;
      KeepAlive = true;
      ThrottleInterval = 60;
      ProcessType = "Background";
      Umask = 63;
      StandardOutPath = "${llmUsageState}/agent.log";
      StandardErrorPath = "${llmUsageState}/agent.err.log";
    };
  };

  launchd.agents.llm-usage-personal = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
    enable = true;
    config = {
      Label = "org.nix-community.home.llm-usage-personal";
      ProgramArguments = ["${llmUsagePersonalAgent}/bin/llm-usage-personal-agent"];
      RunAtLoad = true;
      KeepAlive = true;
      ThrottleInterval = 60;
      ProcessType = "Background";
      Umask = 63;
      StandardOutPath = "${llmUsageState}/personal.log";
      StandardErrorPath = "${llmUsageState}/personal.err.log";
    };
  };

  home.sessionVariables = {
    CLAUDE_CONFIG_DIR = "$HOME/.config/claude-personal";
    CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1";
  };

  home.activation.desktopprPrepareWallpaper = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin
    (lib.hm.dag.entryBetween ["desktoppr"] ["setDarwinDefaults"] ''
      # desktoppr manage adjusts the old image before replacing it, which crashes
      # if that image was garbage-collected. Set the current image first.
      run "${lib.getExe config.programs.desktoppr.package}" all ${lib.escapeShellArg "${solidWallpaper}"}
      if [ -z "''${DRY_RUN:-}" ]; then
        # macOS publishes wallpaper changes asynchronously to other processes.
        wallpaper_ready=false
        for attempt in {1..50}; do
          current_wallpapers="$("${lib.getExe config.programs.desktoppr.package}" all)"
          if [ -n "$current_wallpapers" ] && ! printf '%s\n' "$current_wallpapers" |
            ${pkgs.gnugrep}/bin/grep -Fxqv ${lib.escapeShellArg "${solidWallpaper}"}; then
            wallpaper_ready=true
            break
          fi
          ${pkgs.coreutils}/bin/sleep 0.2
        done
        if [ "$wallpaper_ready" != true ]; then
          echo "Timed out waiting for the managed wallpaper on all displays" >&2
          exit 1
        fi
      fi
    '');

  programs.desktoppr = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
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
    } // lib.optionalAttrs pkgs.stdenv.hostPlatform.isDarwin {
      ".config/rex" = {
        source = ./dotfiles/config/rex;
        recursive = true;
      };
    };
  };
}
