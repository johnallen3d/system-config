{lib, ...}: let
  sketchybarHex = hex: "0xff${lib.removePrefix "#" hex}";

  renderLua = value:
    if builtins.isAttrs value
    then
      let
        fields = builtins.attrNames value;
      in
        "{ ${lib.concatMapStringsSep ", " (name: "[${builtins.toJSON name}] = ${renderLua value.${name}}") fields} }"
    else if builtins.isList value
    then "{ ${lib.concatMapStringsSep ", " renderLua value} }"
    else if builtins.isString value
    then builtins.toJSON value
    else if builtins.isBool value
    then
      if value
      then "true"
      else "false"
    else if builtins.isInt value || builtins.isFloat value
    then builtins.toString value
    else throw "Unsupported Lua value type";

  toLuaModule = value: "return ${renderLua value}\n";

  palettes = {
    moon = {
      bg = "#222436";
      bgDark = "#1e2030";
      bgDark1 = "#191b29";
      bgHighlight = "#2f334d";
      bgVisual = "#2d3f76";
      border = "#1b1d2b";
      black = "#1b1d2b";
      text = "#c8d3f5";
      fg = "#c8d3f5";
      muted = "#828bb8";
      accent = "#82aaff";
      blue = "#82aaff";
      accentText = "#c8d3f5";
      green = "#c3e88d";
      red = "#ff757f";
      orange = "#ff966c";
      yellow = "#ffc777";
      magenta = "#c099ff";
      purple = "#fca7ea";
      cyan = "#86e1fc";
      teal = "#4fd6be";
      gutter = "#3b4261";
      comment = "#636da6";
      cyanBright = "#0db9d7";
      redDark = "#c53b53";
      selectionBar = "#4b3b24";
      yankBar = "#2a4556";
      cutBar = "#4b2a3d";
    };
  };

  themeRoles = let
    c = palettes.moon;
  in {
    ui = {
      bg = c.bg;
      bg_alt = c.bgDark;
      bg_dark = c.bgDark1;
      fg = c.fg;
      muted = c.muted;
      border = c.border;
      selection = c.bgVisual;
      cursorline = c.bgHighlight;
      float = c.bgDark;
      pmenu = c.bgDark;
      pmenu_sel = c.bgHighlight;
      search = c.selectionBar;
      inc_search = c.orange;
    };

    syntax = {
      comment = c.comment;
      string = c.green;
      number = c.orange;
      keyword = c.magenta;
      function = c.cyan;
      type = c.yellow;
      constant = c.purple;
      operator = c.cyanBright;
      parameter = c.text;
      property = c.teal;
      variable = c.text;
      builtin = c.blue;
      preproc = c.red;
    };

    diagnostics = {
      error = c.red;
      warn = c.yellow;
      info = c.blue;
      hint = c.teal;
      ok = c.green;
    };

    vcs = {
      added = c.green;
      changed = c.blue;
      removed = c.red;
    };

    diff = {
      add_bg = "#273849";
      change_bg = "#253b4d";
      delete_bg = "#3a273a";
      text_bg = "#394b70";
    };
  };

  elioTheme = let
    c = palettes.moon;
  in {
    palette = {
      bg = c.bg;
      chrome = c.bgDark;
      chrome_alt = c.bgDark1;
      panel = c.bgDark;
      panel_alt = c.bgDark1;
      surface = c.bgHighlight;
      elevated = c.bgHighlight;
      border = c.border;
      text = c.text;
      muted = c.muted;
      accent = c.accent;
      accent_soft = c.bgHighlight;
      accent_text = c.accentText;
      selected_bg = c.bgVisual;
      selected_border = c.accent;
      selection_bar = c.yellow;
      yank_bar = c.green;
      cut_bar = c.red;
      grid_selection_band = c.selectionBar;
      grid_yank_band = c.yankBar;
      grid_cut_band = c.cutBar;
      sidebar_active = c.bgHighlight;
      button_bg = c.bg;
      button_disabled_bg = c.bgDark;
      path_bg = c.bgDark;
    };

    preview.code = {
      fg = c.text;
      bg = c.bgDark;
      selection_bg = c.bgVisual;
      selection_fg = c.accentText;
      caret = c.accent;
      line_highlight = c.bgDark1;
      line_number = c.gutter;
      comment = c.comment;
      string = c.green;
      constant = c.orange;
      keyword = c.magenta;
      function = c.cyan;
      type = c.yellow;
      parameter = c.purple;
      tag = c.teal;
      operator = c.cyanBright;
      macro = c.red;
      invalid = c.redDark;
    };

    classes = {
      directory.color = c.accent;
      code.color = c.cyan;
      config.color = c.magenta;
      document.color = c.green;
      license.color = c.yellow;
      image.color = c.teal;
      audio.color = c.orange;
      video.color = c.red;
      archive.color = c.orange;
      font.color = c.purple;
      data.color = c.green;
      file.color = c.text;
    };

    directories = {
      "node_modules" = {icon = "󰏗"; color = c.accent;};
      "tests" = {icon = "󰉋"; color = c.accent;};
      "test" = {icon = "󰉋"; color = c.accent;};
      "__tests__" = {icon = "󰉋"; color = c.accent;};
      "scripts" = {icon = "󰉋"; color = c.accent;};
      "build" = {icon = "󰉋"; color = c.accent;};
      "dist" = {icon = "󰉋"; color = c.accent;};
      ".next" = {icon = ""; color = c.accent;};
      ".nuxt" = {icon = "󱄆"; color = c.accent;};
      ".svelte-kit" = {icon = ""; color = c.accent;};
      ".astro" = {icon = ""; color = c.accent;};
      "public" = {icon = "󰉋"; color = c.accent;};
      "Public" = {icon = "󰉋"; color = c.accent;};
      "pictures" = {icon = "󰉏"; color = c.teal;};
      "Pictures" = {icon = "󰉏"; color = c.teal;};
      "documents" = {icon = "󰲃"; color = c.green;};
      "Documents" = {icon = "󰲃"; color = c.green;};
      "downloads" = {icon = "󰉍"; color = c.yellow;};
      "Downloads" = {icon = "󰉍"; color = c.yellow;};
      "music" = {icon = "󱍙"; color = c.magenta;};
      "Music" = {icon = "󱍙"; color = c.magenta;};
      "videos" = {icon = "󰕧"; color = c.red;};
      "Videos" = {icon = "󰕧"; color = c.red;};
      "desktop" = {icon = "󰟀"; color = c.text;};
      "Desktop" = {icon = "󰟀"; color = c.text;};
    };

    files = {
      "README.md" = {icon = "󰍔"; color = c.green;};
      "LICENSE" = {icon = "󰿃"; color = c.yellow;};
    };
  };
  nvimTheme = {
    palette = palettes.moon;
    roles = themeRoles;
  };
in {
  inherit palettes;

  inherit elioTheme;
  inherit nvimTheme;

  nvimLua = toLuaModule nvimTheme;

  sketchybarMoonSh = let
    c = palettes.moon;
  in ''
    bracket_background_color="${sketchybarHex c.bg}"       # bg
    default_label_color="${sketchybarHex c.fg}"            # white
    default_icon_color="${sketchybarHex c.fg}"             # white
    highlight_icon_color="${sketchybarHex c.green}"        # green
    bracket_border_color="0x00000000" # transparent
    current_app_background_color="${sketchybarHex c.blue}"   # blue
    current_app_color="${sketchybarHex c.black}"              # black
    music_highlight="${sketchybarHex c.green}"                # green
    cpu_highlight="${sketchybarHex c.blue}"                  # blue
    weather_highlight="${sketchybarHex c.yellow}"            # yellow
    date_highlight="${sketchybarHex c.magenta}"              # magenta
    time_highlight="${sketchybarHex c.cyan}"                 # cyan
  '';
}
