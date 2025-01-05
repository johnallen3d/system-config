{...}: let
  makeFontConfig = {
    family,
    normalStyle ? "SemiBold",
    boldStyle ? "Bold",
    italicStyle ? "SemiBold Italic",
    size ? 15.0,
  }: {
    normal = {
      inherit family;
      style = normalStyle;
    };
    bold = {
      inherit family;
      style = boldStyle;
    };
    italic = {
      inherit family;
      style = italicStyle;
    };
    inherit size;
  };

  fonts = {
    fira = makeFontConfig {
      family = "FiraCode Nerd Font";
    };
    jetbrains = makeFontConfig {
      family = "JetBrainsMono Nerd Font";
      size = 15.5;
    };
    monaspice = makeFontConfig {
      family = "MonaspiceXe Nerd Font Mono";
      normalStyle = "Medium";
      boldStyle = "Bold";
      italicStyle = "Bold Italic";
      size = 15.5;
    };
  };

  selectedFont = fonts.jetbrains;
in {
  programs.alacritty = {
    enable = true;
    settings = {
      env = {
        TERM = "xterm-256color";
      };

      # shell = {
      #   program = "/etc/profiles/per-user/john.allen/bin/fish";
      #   args = ["-l" "-c" "zellij"];
      # };

      window = {
        decorations = "Buttonless";
        dynamic_padding = true;
        option_as_alt = "Both";
        padding = {
          x = 4;
          y = 4;
        };
      };

      # tips: run to see a list of installed fonts
      #   - on linux `fc-list`
      #   - on macos: `atsutil fonts -list`
      font = {
        normal = selectedFont.normal;
        bold = selectedFont.bold;
        italic = selectedFont.italic;
        size = selectedFont.size;
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
