{...}: {
  programs.alacritty = {
    enable = true;
    settings = {
      env = {
        TERM = "screen-256color";
      };

      window = {
        padding = {
          x = 2;
          y = 2;
        };
      };

      # tip - on linux run `fc-list` to see a list of installed fonts
      font = {
        normal = {
          family = "Monaspace Xenon SemiBold";
        };
        bold = {
          family = "Monaspace Neon Bold";
        };
        italic = {
          family = "Monaspace Radon SemiBold Italic";
        };
        size = 8.0;
      };

      colors = {
        draw_bold_text_with_bright_colors = true;

        primary = {
          background = "#222436";
          foreground = "#c8d3f5";
        };

        cursor = {
          cursor = "#c8d3f5";
          text = "#222436";
        };

        normal = {
          black = "#1b1d2b";
          red = "#ff757f";
          green = "#c3e88d";
          yellow = "#ffc777";
          blue = "#82aaff";
          magenta = "#c099ff";
          cyan = "#86e1fc";
          white = "#828bb8";
        };

        bright = {
          black = "#444a73";
          red = "#ff757f";
          green = "#c3e88d";
          yellow = "#ffc777";
          blue = "#82aaff";
          magenta = "#c099ff";
          cyan = "#86e1fc";
          white = "#c8d3f5";
        };

        # [[colors.indexed_colors]]
        # index = 16
        # color = "#ff966c"

        # [[colors.indexed_colors]]
        # index = 17
        # color = "#c53b53"
      };
    };
  };
}
