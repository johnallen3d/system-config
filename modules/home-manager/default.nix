{
  pkgs,
  brew_bin,
  ...
}: {
  home.stateVersion = "24.05";

  imports = [
    ./packages
  ];

  home = {
    sessionPath = [
      "${pkgs.path}"
      "/etc/profiles/per-user/$USER/bin/"
      "/usr/local/bin"
      "$HOME/bin"
      "$HOME/.local/bin"
      "$HOME/.cargo/bin"
      "/run/current-system/sw/bin"
      "${brew_bin}"
    ];

    file = {
      ".ctags".source = ./dotfiles/ctags;
      ".irbrc".source = ./dotfiles/irbrc;
      ".pryrc".source = ./dotfiles/pryrc;

      ".config/stylua.toml".source = ./dotfiles/config/stylua.toml;

      ".config" = {
        recursive = true;
        source = ./dotfiles/config;
      };

      "bin" = {
        recursive = true;
        source = ./dotfiles/bin;
      };

      # bin = {
      #   "bottombar".source = config.lib.file.mkOutOfStoreSymlink ./some-source-file;
      # };

      "Library/Application Support/org.dystroy.bacon/prefs.toml".source = ./dotfiles/bacon-prefs.toml;

      # TODO: this is tricky!
      # "Library/Fonts/Font\ Awesome\ 6\ Brands-Regular-400.otf".source = "../../../Library/CloudStorage/Dropbox/Fonts/Font Awesome 6 Brands-Regular-400.otf";
      # "Font Awesome 6 Duotone-Solid-900.otf".source = ;
      # "Font Awesome 6 Pro-Light-300.otf".source = ;
      # "Font Awesome 6 Pro-Regular-400.otf".source = ;
      # "Font Awesome 6 Pro-Solid-900.otf".source = ;
      # "Font Awesome 6 Pro-Thin-100.otf".source = ;
      # "Font Awesome 6 Sharp-Regular-400.otf".source = ;
      # "Font Awesome 6 Sharp-Solid-900.otf".source = ;
    };
  };
}
