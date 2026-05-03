{
  lib,
  pkgs,
  ...
}: let
  common = import ../common/common.nix {inherit pkgs;};
  musicDir = common.commonVariables.MUSIC_DIR;
in {
  home.stateVersion = "24.05";

  imports = [
    ./packages
    ./pi-extensions.nix
    ./pi-prompts.nix
    ./pi-settings.nix
  ];

  home.sessionVariables = {
    CLAUDE_CONFIG_DIR = "$HOME/.config/claude-personal";
    CLAUDE_CODE_DISABLE_1M_CONTEXT = "1";
    CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS = "1";
  };

  home = {
    activation.claudeCodeSymlink = lib.hm.dag.entryAfter ["writeBoundary"] ''
      if [ -x /opt/homebrew/bin/claude ]; then
        mkdir -p "$HOME/.local/bin"
        ln -snf /opt/homebrew/bin/claude "$HOME/.local/bin/claude"
      fi
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

      "Library/Application Support/elio/theme.toml".text = ''
        [palette]
        bg = "#1a1b26"
        chrome = "#16161e"
        chrome_alt = "#11121a"
        panel = "#1f2335"
        panel_alt = "#16161e"
        surface = "#24283b"
        elevated = "#292e42"
        border = "#414868"
        text = "#c0caf5"
        muted = "#a9b1d6"
        accent = "#7aa2f7"
        accent_soft = "#24283b"
        accent_text = "#e0e8ff"
        selected_bg = "#283457"
        selected_border = "#7aa2f7"
        selection_bar = "#ff9e64"
        yank_bar = "#9ece6a"
        cut_bar = "#f7768e"
        grid_selection_band = "#38280e"
        grid_yank_band = "#1c3816"
        grid_cut_band = "#3c1422"
        sidebar_active = "#24283b"
        button_bg = "#1a1b26"
        button_disabled_bg = "#16161e"
        path_bg = "#1f2335"

        [preview.code]
        fg = "#c0caf5"
        bg = "#16161e"
        selection_bg = "#283457"
        selection_fg = "#e0e8ff"
        caret = "#7aa2f7"
        line_highlight = "#1a1b26"
        line_number = "#565f89"
        comment = "#565f89"
        string = "#9ece6a"
        constant = "#ff9e64"
        keyword = "#bb9af7"
        function = "#7dcfff"
        type = "#e0af68"
        parameter = "#f5c2e7"
        tag = "#73daca"
        operator = "#2ac3de"
        macro = "#f7768e"
        invalid = "#db4b4b"

        [classes.directory]
        color = "#7aa2f7"

        [classes.code]
        color = "#7dcfff"

        [classes.config]
        color = "#bb9af7"

        [classes.document]
        color = "#9ece6a"

        [classes.license]
        color = "#e0af68"

        [classes.image]
        color = "#73daca"

        [classes.audio]
        color = "#ff9e64"

        [classes.video]
        color = "#f7768e"

        [classes.archive]
        color = "#ff9e64"

        [classes.font]
        color = "#9d7cd8"

        [classes.data]
        color = "#9ece6a"

        [classes.file]
        color = "#c0caf5"

        [directories."node_modules"]
        icon = "󰏗"
        color = "#7aa2f7"

        [directories."tests"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."test"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."__tests__"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."scripts"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."build"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."dist"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories.".next"]
        icon = ""
        color = "#7aa2f7"

        [directories.".nuxt"]
        icon = "󱄆"
        color = "#7aa2f7"

        [directories.".svelte-kit"]
        icon = ""
        color = "#7aa2f7"

        [directories.".astro"]
        icon = ""
        color = "#7aa2f7"

        [directories."public"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."Public"]
        icon = "󰉋"
        color = "#7aa2f7"

        [directories."pictures"]
        icon = "󰉏"
        color = "#73daca"

        [directories."Pictures"]
        icon = "󰉏"
        color = "#73daca"

        [directories."documents"]
        icon = "󰲃"
        color = "#9ece6a"

        [directories."Documents"]
        icon = "󰲃"
        color = "#9ece6a"

        [directories."downloads"]
        icon = "󰉍"
        color = "#e0af68"

        [directories."Downloads"]
        icon = "󰉍"
        color = "#e0af68"

        [directories."music"]
        icon = "󱍙"
        color = "#bb9af7"

        [directories."Music"]
        icon = "󱍙"
        color = "#bb9af7"

        [directories."videos"]
        icon = "󰕧"
        color = "#f7768e"

        [directories."Videos"]
        icon = "󰕧"
        color = "#f7768e"

        [directories."desktop"]
        icon = "󰟀"
        color = "#c0caf5"

        [directories."Desktop"]
        icon = "󰟀"
        color = "#c0caf5"

        [files."README.md"]
        icon = "󰍔"
        color = "#9ece6a"

        [files."LICENSE"]
        icon = "󰿃"
        color = "#e0af68"
      '';

      ".config" = {
        recursive = true;
        source = ./dotfiles/config;
      };

      "bin" = {
        recursive = true;
        source = ./dotfiles/bin;
      };

      "bin/bottombar".source = "${pkgs.sketchybar}/bin/sketchybar";

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
    };
  };
}
