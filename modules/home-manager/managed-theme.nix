{lib, ...}: let
  sketchybarHex = hex: "0xff${lib.removePrefix "#" hex}";

  renderLua = value:
    if builtins.isAttrs value
    then let
      fields = builtins.attrNames value;
    in "{ ${lib.concatMapStringsSep ", " (name: "[${builtins.toJSON name}] = ${renderLua value.${name}}") fields} }"
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
  toPrettyJson = value: builtins.toJSON value;

  # Change this single value to switch managed theme consumers.
  # Current theme: rose-pine-moon.
  # Available: catppuccin-mocha, moon, nord-polar-night, rose-pine, rose-pine-moon, storm.
  activeVariant = "rose-pine-moon";

  themeFamily = variant:
    if lib.hasPrefix "catppuccin-" variant
    then "catppuccin"
    else if lib.hasPrefix "nord-" variant
    then "nord"
    else if lib.hasPrefix "rose-pine" variant
    then "rose-pine"
    else "tokyo-night";
  isCatppuccin = variant: themeFamily variant == "catppuccin";
  isNord = variant: themeFamily variant == "nord";
  isRosePine = variant: themeFamily variant == "rose-pine";
  themeName = variant:
    if isCatppuccin variant || isRosePine variant
    then variant
    else if isNord variant
    then "nord"
    else "tokyonight-${variant}";
  hyphenThemeName = variant:
    if isCatppuccin variant || isRosePine variant
    then variant
    else if isNord variant
    then "nord"
    else "tokyo-night-${variant}";
  batThemeName = variant:
    if isCatppuccin variant
    then "Catppuccin Mocha"
    else if isNord variant
    then "Nord"
    else if variant == "rose-pine-moon"
    then "Rose Pine Moon"
    else if isRosePine variant
    then "Rose Pine"
    else "tokyonight_${variant}";
  stripHex = hex: lib.removePrefix "#" hex;

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
      borderBright = "#545c7e";
      bgPurple = "#262335";
      terminalBrightBlack = "#444a73";
      terminalBrightRed = "#ff8d94";
      terminalBrightGreen = "#c7fb6d";
      terminalBrightYellow = "#ffd8ab";
      terminalBrightBlue = "#9ab8ff";
      terminalBrightMagenta = "#caabff";
      terminalBrightCyan = "#b2ebff";
      terminalWhite = "#828bb8";
      terminalBrightWhite = "#c8d3f5";
    };

    storm = {
      bg = "#24283b";
      bgDark = "#1f2335";
      bgDark1 = "#1b1e2d";
      bgHighlight = "#292e42";
      bgVisual = "#2e3c64";
      border = "#1d202f";
      black = "#1d202f";
      text = "#c0caf5";
      fg = "#c0caf5";
      muted = "#737aa2";
      accent = "#7aa2f7";
      blue = "#7aa2f7";
      accentText = "#c0caf5";
      green = "#9ece6a";
      red = "#f7768e";
      orange = "#ff9e64";
      yellow = "#e0af68";
      magenta = "#bb9af7";
      purple = "#9d7cd8";
      cyan = "#7dcfff";
      teal = "#1abc9c";
      gutter = "#3b4261";
      comment = "#565f89";
      cyanBright = "#0db9d7";
      redDark = "#db4b4b";
      selectionBar = "#3d59a1";
      yankBar = "#2b485a";
      cutBar = "#52313f";
      borderBright = "#545c7e";
      bgPurple = "#24283b";
      terminalBrightBlack = "#414868";
      terminalBrightRed = "#ff899d";
      terminalBrightGreen = "#9fe044";
      terminalBrightYellow = "#faba4a";
      terminalBrightBlue = "#8db0ff";
      terminalBrightMagenta = "#c7a9ff";
      terminalBrightCyan = "#a4daff";
      terminalWhite = "#a9b1d6";
      terminalBrightWhite = "#c0caf5";
    };

    catppuccin-mocha = {
      bg = "#1e1e2e";
      bgDark = "#181825";
      bgDark1 = "#11111b";
      bgHighlight = "#313244";
      bgVisual = "#45475a";
      border = "#11111b";
      black = "#11111b";
      text = "#cdd6f4";
      fg = "#cdd6f4";
      muted = "#7f849c";
      accent = "#89b4fa";
      blue = "#89b4fa";
      accentText = "#cdd6f4";
      green = "#a6e3a1";
      red = "#f38ba8";
      orange = "#fab387";
      yellow = "#f9e2af";
      magenta = "#cba6f7";
      purple = "#f5c2e7";
      cyan = "#89dceb";
      teal = "#94e2d5";
      gutter = "#45475a";
      comment = "#6c7086";
      cyanBright = "#74c7ec";
      redDark = "#eba0ac";
      selectionBar = "#45475a";
      yankBar = "#2e473b";
      cutBar = "#4a2f3a";
      borderBright = "#6c7086";
      bgPurple = "#1e1e2e";
      terminalBrightBlack = "#585b70";
      terminalBrightRed = "#f38ba8";
      terminalBrightGreen = "#a6e3a1";
      terminalBrightYellow = "#f9e2af";
      terminalBrightBlue = "#89b4fa";
      terminalBrightMagenta = "#cba6f7";
      terminalBrightCyan = "#89dceb";
      terminalWhite = "#bac2de";
      terminalBrightWhite = "#cdd6f4";
    };

    nord-polar-night = {
      bg = "#2E3440";
      bgDark = "#3B4252";
      bgDark1 = "#2E3440";
      bgHighlight = "#434C5E";
      bgVisual = "#4C566A";
      border = "#3B4252";
      black = "#2E3440";
      text = "#ECEFF4";
      fg = "#ECEFF4";
      muted = "#D8DEE9";
      accent = "#88C0D0";
      blue = "#81A1C1";
      accentText = "#ECEFF4";
      green = "#A3BE8C";
      red = "#BF616A";
      orange = "#D08770";
      yellow = "#EBCB8B";
      magenta = "#B48EAD";
      purple = "#B48EAD";
      cyan = "#88C0D0";
      teal = "#8FBCBB";
      gutter = "#4C566A";
      comment = "#4C566A";
      cyanBright = "#8FBCBB";
      redDark = "#D08770";
      selectionBar = "#434C5E";
      yankBar = "#A3BE8C";
      cutBar = "#BF616A";
      borderBright = "#4C566A";
      bgPurple = "#3B4252";
      terminalBrightBlack = "#4C566A";
      terminalBrightRed = "#BF616A";
      terminalBrightGreen = "#A3BE8C";
      terminalBrightYellow = "#EBCB8B";
      terminalBrightBlue = "#81A1C1";
      terminalBrightMagenta = "#B48EAD";
      terminalBrightCyan = "#88C0D0";
      terminalWhite = "#D8DEE9";
      terminalBrightWhite = "#ECEFF4";
    };

    rose-pine = {
      bg = "#191724";
      bgDark = "#1F1D2E";
      bgDark1 = "#16141F";
      bgHighlight = "#26233A";
      bgVisual = "#403D52";
      border = "#26233A";
      black = "#16141F";
      text = "#E0DEF4";
      fg = "#E0DEF4";
      muted = "#908CAA";
      accent = "#C4A7E7";
      blue = "#9CCFD8";
      accentText = "#191724";
      green = "#31748F";
      red = "#EB6F92";
      orange = "#EBBCBA";
      yellow = "#F6C177";
      magenta = "#C4A7E7";
      purple = "#C4A7E7";
      cyan = "#9CCFD8";
      teal = "#31748F";
      gutter = "#524F67";
      comment = "#6E6A86";
      cyanBright = "#9CCFD8";
      redDark = "#B4637A";
      selectionBar = "#403D52";
      yankBar = "#2A4A5E";
      cutBar = "#4E2638";
      borderBright = "#524F67";
      bgPurple = "#1F1D2E";
      terminalBrightBlack = "#6E6A86";
      terminalBrightRed = "#EB6F92";
      terminalBrightGreen = "#31748F";
      terminalBrightYellow = "#F6C177";
      terminalBrightBlue = "#9CCFD8";
      terminalBrightMagenta = "#C4A7E7";
      terminalBrightCyan = "#9CCFD8";
      terminalWhite = "#908CAA";
      terminalBrightWhite = "#E0DEF4";
    };

    rose-pine-moon = {
      bg = "#232136";
      bgDark = "#2A273F";
      bgDark1 = "#1F1D2E";
      bgHighlight = "#393552";
      bgVisual = "#44415A";
      border = "#393552";
      black = "#1F1D2E";
      text = "#E0DEF4";
      fg = "#E0DEF4";
      muted = "#908CAA";
      accent = "#C4A7E7";
      blue = "#9CCFD8";
      accentText = "#232136";
      green = "#3E8FB0";
      red = "#EB6F92";
      orange = "#EA9A97";
      yellow = "#F6C177";
      magenta = "#C4A7E7";
      purple = "#C4A7E7";
      cyan = "#9CCFD8";
      teal = "#3E8FB0";
      gutter = "#56526E";
      comment = "#6E6A86";
      cyanBright = "#9CCFD8";
      redDark = "#B4637A";
      selectionBar = "#44415A";
      yankBar = "#305B70";
      cutBar = "#4E2638";
      borderBright = "#56526E";
      bgPurple = "#2A273F";
      terminalBrightBlack = "#6E6A86";
      terminalBrightRed = "#EB6F92";
      terminalBrightGreen = "#3E8FB0";
      terminalBrightYellow = "#F6C177";
      terminalBrightBlue = "#9CCFD8";
      terminalBrightMagenta = "#C4A7E7";
      terminalBrightCyan = "#9CCFD8";
      terminalWhite = "#908CAA";
      terminalBrightWhite = "#E0DEF4";
    };
  };

  variantNames = builtins.attrNames palettes;

  mkThemeRoles = c: {
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
      add_bg = c.yankBar;
      change_bg = c.bgHighlight;
      delete_bg = c.cutBar;
      text_bg = c.bgVisual;
    };
  };

  mkTelegramTheme = c: ''
    // Generated from modules/home-manager/managed-theme.nix.
    // Telegram bootstrap: choose this file once in Telegram via
    // Settings -> Chat Settings -> Chat Wallpaper -> Choose from file.
    // Telegram will reload this file on launch, but initial selection remains manual.

    accentColor: ${c.accent};
    accentColorText: ${c.accentText};
    bgColor: ${c.bg};
    bgAltColor: ${c.bgDark};
    bgHoverColor: ${c.bgHighlight};
    bgActiveColor: ${c.bgVisual};
    textColor: ${c.text};
    mutedColor: ${c.muted};
    blueColor: ${c.blue};
    greenColor: ${c.green};
    redColor: ${c.red};
    yellowColor: ${c.yellow};
    purpleColor: ${c.purple};
    tealColor: ${c.teal};
    borderColor: ${c.border};

    windowBg: bgColor;
    windowFg: textColor;
    windowBgOver: bgHoverColor;
    windowBgActive: accentColor;
    windowFgActive: accentColorText;
    windowSubTextFg: mutedColor;
    windowSubTextFgOver: textColor;
    windowBoldFg: textColor;
    windowBoldFgOver: textColor;
    windowActiveTextFg: blueColor;
    windowBorderFg: borderColor;
    windowBorderWhiteFg: bgAltColor;
    windowBgRipple: bgActiveColor;
    windowBgSplash: bgAltColor;
    windowShadowFg: borderColor;

    dialogsBg: bgAltColor;
    dialogsBgOver: bgHoverColor;
    dialogsBgActive: accentColor;
    dialogsBgPinned: bgHoverColor;
    dialogsBgPinnedActive: accentColor;
    dialogsNameFg: textColor;
    dialogsNameFgOver: textColor;
    dialogsNameFgActive: accentColorText;
    dialogsTextFg: mutedColor;
    dialogsTextFgOver: textColor;
    dialogsTextFgActive: accentColorText;
    dialogsDateFg: mutedColor;
    dialogsDateFgOver: textColor;
    dialogsDateFgActive: accentColorText;
    dialogsUnreadBadgeBg: accentColor;
    dialogsUnreadBadgeFg: accentColorText;
    dialogsUnreadBadgeMutedBg: bgHoverColor;
    dialogsUnreadBadgeMutedFg: mutedColor;
    dialogsSentIconFg: blueColor;
    dialogsVerifiedIconBg: blueColor;
    dialogsVerifiedIconFg: bgColor;

    historyTextInFg: textColor;
    historyTextOutFg: textColor;
    historyLinkInFg: blueColor;
    historyLinkOutFg: blueColor;
    historyFileNameInFg: blueColor;
    historyFileNameOutFg: blueColor;
    historyOutIconFg: blueColor;
    historyOutIconFgSelected: blueColor;
    historyOutSentFg: blueColor;
    historyOutSentFgSelected: blueColor;
    historyOutViewsFg: mutedColor;
    historyOutViewsFgSelected: textColor;
    historyInDateFg: mutedColor;
    historyOutDateFg: mutedColor;
    historyInDateFgSelected: textColor;
    historyOutDateFgSelected: textColor;
    historyReplyLineFg: purpleColor;
    historyReplyNameFg: purpleColor;
    historyReplyTextFg: mutedColor;
    historyReplyInvertedLineFg: accentColorText;
    historyReplyInvertedNameFg: accentColorText;
    historyReplyInvertedTextFg: accentColorText;

    msgInBg: bgHoverColor;
    msgInBgSelected: bgActiveColor;
    msgOutBg: bgAltColor;
    msgOutBgSelected: bgActiveColor;
    msgSelectOverlay: borderColor;
    msgStickerOverlay: borderColor;

    historyComposeAreaBg: bgHoverColor;
    historyComposeAreaFg: textColor;
    historyComposeAreaFgService: mutedColor;
    historyComposeAreaBgActive: bgAltColor;
    historyComposeAreaBorderFg: borderColor;
    historyScrollBarBg: bgHoverColor;
    historyScrollBarBgOver: bgActiveColor;
    historyScrollBg: bgColor;
    historyUnreadBarBg: accentColor;
    historyUnreadBarFg: accentColorText;
    historyToDownBg: accentColor;
    historyToDownBgOver: purpleColor;
    historyToDownFg: accentColorText;

    emojiPanBg: bgAltColor;
    emojiPanCategories: bgHoverColor;
    emojiPanHeaderFg: mutedColor;

    overviewBg: bgColor;
    overviewPhotoSelectOverlay: borderColor;
  '';

  mkElioTheme = c: {
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
      "node_modules" = {
        icon = "󰏗";
        color = c.accent;
      };
      "tests" = {
        icon = "󰉋";
        color = c.accent;
      };
      "test" = {
        icon = "󰉋";
        color = c.accent;
      };
      "__tests__" = {
        icon = "󰉋";
        color = c.accent;
      };
      "scripts" = {
        icon = "󰉋";
        color = c.accent;
      };
      "build" = {
        icon = "󰉋";
        color = c.accent;
      };
      "dist" = {
        icon = "󰉋";
        color = c.accent;
      };
      ".next" = {
        icon = "";
        color = c.accent;
      };
      ".nuxt" = {
        icon = "󱄆";
        color = c.accent;
      };
      ".svelte-kit" = {
        icon = "";
        color = c.accent;
      };
      ".astro" = {
        icon = "";
        color = c.accent;
      };
      "public" = {
        icon = "󰉋";
        color = c.accent;
      };
      "Public" = {
        icon = "󰉋";
        color = c.accent;
      };
      "pictures" = {
        icon = "󰉏";
        color = c.teal;
      };
      "Pictures" = {
        icon = "󰉏";
        color = c.teal;
      };
      "documents" = {
        icon = "󰲃";
        color = c.green;
      };
      "Documents" = {
        icon = "󰲃";
        color = c.green;
      };
      "downloads" = {
        icon = "󰉍";
        color = c.yellow;
      };
      "Downloads" = {
        icon = "󰉍";
        color = c.yellow;
      };
      "music" = {
        icon = "󱍙";
        color = c.magenta;
      };
      "Music" = {
        icon = "󱍙";
        color = c.magenta;
      };
      "videos" = {
        icon = "󰕧";
        color = c.red;
      };
      "Videos" = {
        icon = "󰕧";
        color = c.red;
      };
      "desktop" = {
        icon = "󰟀";
        color = c.text;
      };
      "Desktop" = {
        icon = "󰟀";
        color = c.text;
      };
    };

    files = {
      "README.md" = {
        icon = "󰍔";
        color = c.green;
      };
      "LICENSE" = {
        icon = "󰿃";
        color = c.yellow;
      };
    };
  };

  mkNeovimTheme = variant:
    if builtins.elem variant ["moon" "storm"]
    then {
      plugin = {
        src = "https://github.com/folke/tokyonight.nvim";
        module = "tokyonight";
        setup = {
          style = variant;
        };
      };
      colorscheme = "tokyonight-${variant}";
    }
    else if variant == "catppuccin-mocha"
    then {
      plugin = {
        src = "https://github.com/catppuccin/nvim";
        module = "catppuccin";
        setup = {
          flavour = "mocha";
        };
      };
      colorscheme = "catppuccin";
    }
    else if variant == "nord-polar-night"
    then {
      plugin = {
        src = "https://github.com/dupeiran001/nord.nvim";
        module = "nord";
        setup = {
          style = "dark";
        };
      };
      colorscheme = "nord-night";
    }
    else if builtins.elem variant ["rose-pine" "rose-pine-moon"]
    then {
      plugin = {
        src = "https://github.com/rose-pine/neovim";
        module = "rose-pine";
        setup = {
          variant = if variant == "rose-pine-moon" then "moon" else "main";
          dark_variant = if variant == "rose-pine-moon" then "moon" else "main";
        };
      };
      colorscheme = "rose-pine";
    }
    else throw "Unsupported Neovim theme variant: ${variant}";

  mkPiTheme = variant: c: {
    "$schema" = "https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/src/modes/interactive/theme/theme-schema.json";
    name = themeName variant;
    vars = {
      bg = c.bgDark;
      bgDark = c.black;
      bgHighlight = c.bgHighlight;
      border = c.gutter;
      borderBright = c.borderBright;
      muted = c.muted;
      text = c.text;
      blue = c.blue;
      cyan = c.cyan;
      magenta = c.magenta;
      orange = c.orange;
      yellow = c.yellow;
      green = c.green;
      red = c.red;
      teal = c.teal;
      bgPurple = c.bgPurple;
    };
    colors = {
      accent = "blue";
      border = "border";
      borderAccent = "blue";
      borderMuted = "border";
      success = "green";
      error = "red";
      warning = "orange";
      muted = "muted";
      dim = "borderBright";
      text = "";
      thinkingText = "muted";
      selectedBg = "bgHighlight";
      userMessageBg = "bgHighlight";
      userMessageText = "";
      customMessageBg = "bg";
      customMessageText = "";
      customMessageLabel = "magenta";
      toolPendingBg = "bg";
      toolSuccessBg = "bg";
      toolErrorBg = "bg";
      toolTitle = "";
      toolOutput = "muted";
      mdHeading = "magenta";
      mdLink = "blue";
      mdLinkUrl = "cyan";
      mdCode = "green";
      mdCodeBlock = "";
      mdCodeBlockBorder = "border";
      mdQuote = "yellow";
      mdQuoteBorder = "border";
      mdHr = "border";
      mdListBullet = "cyan";
      toolDiffAdded = "teal";
      toolDiffRemoved = "red";
      toolDiffContext = "muted";
      syntaxComment = "muted";
      syntaxKeyword = "magenta";
      syntaxFunction = "blue";
      syntaxVariable = "text";
      syntaxString = "green";
      syntaxNumber = "orange";
      syntaxType = "yellow";
      syntaxOperator = "cyan";
      syntaxPunctuation = "text";
      thinkingOff = "border";
      thinkingMinimal = "borderBright";
      thinkingLow = "muted";
      thinkingMedium = "blue";
      thinkingHigh = "magenta";
      thinkingXhigh = "red";
      bashMode = "orange";
    };
    export = {
      pageBg = "bgDark";
      cardBg = "bg";
      infoBg = "bgHighlight";
    };
  };

  mkBatTheme = variant: c: ''
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
      <key>name</key>
      <string>${batThemeName variant}</string>
      <key>settings</key>
      <array>
        <dict>
          <key>settings</key>
          <dict>
            <key>background</key>
            <string>${c.bg}</string>
            <key>foreground</key>
            <string>${c.text}</string>
            <key>caret</key>
            <string>${c.accent}</string>
            <key>selection</key>
            <string>${c.bgVisual}</string>
          </dict>
        </dict>
        <dict><key>scope</key><string>comment</string><key>settings</key><dict><key>foreground</key><string>${c.comment}</string></dict></dict>
        <dict><key>scope</key><string>string</string><key>settings</key><dict><key>foreground</key><string>${c.green}</string></dict></dict>
        <dict><key>scope</key><string>constant.numeric</string><key>settings</key><dict><key>foreground</key><string>${c.orange}</string></dict></dict>
        <dict><key>scope</key><string>keyword</string><key>settings</key><dict><key>foreground</key><string>${c.magenta}</string></dict></dict>
        <dict><key>scope</key><string>entity.name.function</string><key>settings</key><dict><key>foreground</key><string>${c.cyan}</string></dict></dict>
        <dict><key>scope</key><string>entity.name.type,support.type</string><key>settings</key><dict><key>foreground</key><string>${c.yellow}</string></dict></dict>
        <dict><key>scope</key><string>variable,meta.definition.variable</string><key>settings</key><dict><key>foreground</key><string>${c.text}</string></dict></dict>
        <dict><key>scope</key><string>invalid</string><key>settings</key><dict><key>foreground</key><string>${c.red}</string></dict></dict>
      </array>
    </dict>
    </plist>
  '';

  mkGhosttyTheme = c: ''
    # Generated from modules/home-manager/managed-theme.nix.

    palette = 0=${c.black}
    palette = 1=${c.red}
    palette = 2=${c.green}
    palette = 3=${c.yellow}
    palette = 4=${c.blue}
    palette = 5=${c.magenta}
    palette = 6=${c.cyan}
    palette = 7=${c.terminalWhite}
    palette = 8=${c.terminalBrightBlack}
    palette = 9=${c.terminalBrightRed}
    palette = 10=${c.terminalBrightGreen}
    palette = 11=${c.terminalBrightYellow}
    palette = 12=${c.terminalBrightBlue}
    palette = 13=${c.terminalBrightMagenta}
    palette = 14=${c.terminalBrightCyan}
    palette = 15=${c.terminalBrightWhite}

    background = ${c.bg}
    foreground = ${c.text}
    cursor-color = ${c.text}
    selection-background = ${c.bgVisual}
    selection-foreground = ${c.text}
  '';

  mkFishTheme = c: ''
    # Generated from modules/home-manager/managed-theme.nix.
    fish_color_normal ${stripHex c.text}
    fish_color_command ${stripHex c.cyan}
    fish_color_keyword ${stripHex c.magenta}
    fish_color_quote ${stripHex c.yellow}
    fish_color_redirection ${stripHex c.text}
    fish_color_end ${stripHex c.orange}
    fish_color_error ${stripHex c.red}
    fish_color_param ${stripHex c.purple}
    fish_color_comment ${stripHex c.comment}
    fish_color_selection --background=${stripHex c.bgVisual}
    fish_color_search_match --background=${stripHex c.bgVisual}
    fish_color_operator ${stripHex c.green}
    fish_color_escape ${stripHex c.magenta}
    fish_color_autosuggestion ${stripHex c.comment}

    fish_pager_color_progress ${stripHex c.comment}
    fish_pager_color_prefix ${stripHex c.cyan}
    fish_pager_color_completion ${stripHex c.text}
    fish_pager_color_description ${stripHex c.comment}
    fish_pager_color_selected_background --background=${stripHex c.bgVisual}
  '';

  mkSketchybarSh = c: ''
    bracket_background_color="${sketchybarHex c.bgHighlight}"
    default_label_color="${sketchybarHex c.fg}"
    default_icon_color="${sketchybarHex c.fg}"
    highlight_icon_color="${sketchybarHex c.green}"
    bracket_border_color="0x00000000"
    current_app_background_color="${sketchybarHex c.blue}"
    current_app_color="${sketchybarHex c.black}"
    music_highlight="${sketchybarHex c.green}"
    cpu_highlight="${sketchybarHex c.blue}"
    weather_highlight="${sketchybarHex c.yellow}"
    date_highlight="${sketchybarHex c.magenta}"
    time_highlight="${sketchybarHex c.cyan}"
  '';

  mkSketchybarLua = c: ''
    return {
    	black = ${sketchybarHex c.black},
    	white = ${sketchybarHex c.text},
    	red = ${sketchybarHex c.red},
    	green = ${sketchybarHex c.green},
    	blue = ${sketchybarHex c.blue},
    	yellow = ${sketchybarHex c.yellow},
    	orange = ${sketchybarHex c.orange},
    	magenta = ${sketchybarHex c.magenta},
      purple = ${sketchybarHex c.purple},
    	grey = ${sketchybarHex c.muted},
    	cyan = ${sketchybarHex c.cyan},
    	transparent = 0x00000000,
    	bg1 = ${sketchybarHex c.bgHighlight},
    }
  '';

  batThemes = lib.mapAttrs (variant: palette: mkBatTheme variant palette) palettes;
  bordersActiveAccents = lib.mapAttrs (_: palette: sketchybarHex palette.purple) palettes;
  bordersActiveColors = lib.mapAttrs (_: palette: "glow(${sketchybarHex palette.purple})") palettes;
  elioThemes = lib.mapAttrs (_: palette: mkElioTheme palette) palettes;
  telegramThemes = lib.mapAttrs (_: palette: mkTelegramTheme palette) palettes;
  piThemes = lib.mapAttrs (variant: palette: mkPiTheme variant palette) palettes;
  ghosttyThemes = lib.mapAttrs (_: palette: mkGhosttyTheme palette) palettes;
  fishThemes = lib.mapAttrs (_: palette: mkFishTheme palette) palettes;
  sketchybarThemes = lib.mapAttrs (_: palette: mkSketchybarSh palette) palettes;
  sketchybarLuaThemes = lib.mapAttrs (_: palette: mkSketchybarLua palette) palettes;
in {
  inherit activeVariant;
  inherit palettes;
  inherit variantNames;
  inherit themeFamily;
  inherit themeName;
  inherit hyphenThemeName;
  inherit batThemeName;

  activePalette = palettes.${activeVariant};
  activeTheme = {
    variant = activeVariant;
    family = themeFamily activeVariant;
    palette = palettes.${activeVariant};
    name = themeName activeVariant;
    hyphenName = hyphenThemeName activeVariant;
    batName = batThemeName activeVariant;
  };

  activeThemeName = themeName activeVariant;
  activeHyphenThemeName = hyphenThemeName activeVariant;
  activeBatThemeName = batThemeName activeVariant;
  activeBordersActiveAccent = bordersActiveAccents.${activeVariant};
  activeBordersActiveColor = bordersActiveColors.${activeVariant};

  inherit batThemes;
  inherit bordersActiveAccents;
  inherit bordersActiveColors;
  inherit elioThemes;
  inherit fishThemes;
  inherit ghosttyThemes;
  inherit telegramThemes;
  inherit piThemes;
  inherit sketchybarThemes;
  inherit sketchybarLuaThemes;

  batTheme = batThemes.${activeVariant};
  elioTheme = elioThemes.${activeVariant};
  fishTheme = fishThemes.${activeVariant};
  ghosttyTheme = ghosttyThemes.${activeVariant};
  telegramTheme = telegramThemes.${activeVariant};
  neovimTheme = mkNeovimTheme activeVariant;
  neovimThemeLua = toLuaModule (mkNeovimTheme activeVariant);
  piTheme = piThemes.${activeVariant};
  sketchybarThemeSh = sketchybarThemes.${activeVariant};
  sketchybarColorsLua = sketchybarLuaThemes.${activeVariant};

  piThemeJsons = lib.mapAttrs (_: theme: toPrettyJson theme + "\n") piThemes;
}
