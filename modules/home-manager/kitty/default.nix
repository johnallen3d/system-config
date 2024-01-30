{
  pkgs,
  home,
  ...
}: {
  home.packages = with pkgs; [
    kitty-themes
  ];

  programs.kitty = {
    enable = true;
    darwinLaunchOptions = [
      "--single-instance"
      "--directory ~"
      "--listen-on=unix:/tmp/kitty-socket"
    ];
    shellIntegration = {
      enableBashIntegration = false;
      enableFishIntegration = false;
      enableZshIntegration = false;
      mode = "no-cursor";
    };
    theme = "Tokyo Night Moon";
    settings = {
      # include = "colors.conf";

      font_family = "Monaspace Xenon SemiBold";
      italic_font = "Monaspace Radon SemiBold Italic";
      bold_font = "Monaspace Neon Bold";
      bold_italic_font = "Monaspace Krypton Bold Italic";
      font_size = "14.00";

      adjust_line_height = "0";
      adjust_column_width = "0";

      box_drawing_scale = "0.001, 1, 1.5, 2";

      cursor_shape = "underline";
      cursor_blink_interval = "1";
      cursor_stop_blinking_after = "15.0";

      scrollback_lines = "10000";
      scrollback_pager_history_size = "0";
      scrollback_fill_enlarged_window = "no";

      wheel_scroll_multiplier = "3.0";

      url_color = "#0087BD";
      url_style = "curly";
      open_url_with = "default";

      clear_all_mouse_actions = "yes";
      mouse_hide_wait = "0";
      click_interval = "0.5";

      copy_on_select = "no";
      select_by_word_characters = ":@-./_~?&=%+#";

      focus_follows_mouse = "no";
      repaint_delay = "10";
      input_delay = "3";
      sync_to_monitor = "yes";
      visual_bell_duration = "0.0";
      enable_audio_bell = "yes";

      window_margin_width = "0";
      single_window_margin_width = "5";
      window_padding_width = "0 10 0 10";

      tab_bar_edge = "top";
      tab_bar_margin_width = "5.0";
      tab_bar_margin_height = "0.0 0.0";
      tab_bar_style = "separator";
      tab_separator = "\" \"";
      active_tab_font_style = "bold-italic";
      inactive_tab_font_style = "normal";

      shell = ".";
      editor = "nvim";

      close_on_child_death = "no";

      term = "xterm-kitty";

      allow_remote_control = "yes";
      listen_on = "unix:/tmp/kitty";
      shell_integration = "enabled";
      # action_alias = "kitty_scrollback_nvim kitten ${home}/.local/share/lazy-vim/lazy/kitty-scrollback.nvim/python/kitty_scrollback_nvim.py --nvim-args -u NONE +'nnoremap yy \"+yy; nnoremap y \"+y; vnoremap y \"+y'";
      action_alias = "kitty_scrollback_nvim kitten ${home}/.local/share/nvim/lazy/kitty-scrollback.nvim/python/kitty_scrollback_nvim.py";

      confirm_os_window_close = "0";
      macos_titlebar_color = "background";
      hide_window_decorations = "titlebar-only";
      macos_option_as_alt = "yes";
      macos_quit_when_last_window_closed = "yes";
    };
    keybindings = {
      "super+f" = "kitty_scrollback_nvim";
      "super+v" = "paste_from_clipboard";
      "super+c" = "copy_to_clipboard";
      "super+n" = "new_os_window_with_cwd";
      "super+shift+]" = "next_tab";
      "super+shift+[" = "previous_tab";
      "super+t" = "new_tab_with_cwd";
      "super+w" = "close_tab";
      "super+ctrl+]" = "move_tab_forward";
      "super+ctrl+[" = "move_tab_backward";
      "super+1" = "goto_tab 1";
      "super+2" = "goto_tab 2";
      "super+3" = "goto_tab 3";
      "super+4" = "goto_tab 4";
      "super+5" = "goto_tab 5";
      "super+6" = "goto_tab 6";
      "super+7" = "goto_tab 7";
      "super+8" = "goto_tab 8";
      "super+9" = "goto_tab 9";
      "super+equal" = "change_font_size all +1.0";
      "super+minus" = "change_font_size all -1.0";
      "super+0" = "change_font_size all 0";
      "ctrl+shift+equal" = "change_font_size current +1.0";
      "ctrl+shift+minus" = "change_font_size current -1.0";
      "ctrl+shift+0" = "change_font_size current 0";
      "super+enter" = "noop";
    };
    extraConfig = ''
      font_features MonaspaceXenon-SemiBold       calt liga dlig ss01 ss02 ss03 ss04 ss05 ss06 ss07 ss08
      font_features MonaspaceRadon-SemiBoldItalic calt liga dlig ss01 ss02 ss03 ss04 ss05 ss06 ss07 ss08
      font_features MonaspaceNeon-Bold            calt liga dlig ss01 ss02 ss03 ss04 ss05 ss06 ss07 ss08
      font_features MonaspaceKrypton-BoldItalic   calt liga dlig ss01 ss02 ss03 ss04 ss05 ss06 ss07 ss08

      modify_font underline_thickness 1
      modify_font underline_position 1
      modify_font cell_height +6px

      mouse_map cmd+left press ungrabbed,grabbed mouse_click_url
      mouse_map left press ungrabbed mouse_selection normal
      mouse_map left doublepress ungrabbed mouse_selection word
      mouse_map left triplepress ungrabbed mouse_selection line

    '';
  };
}
