{pkgs, ...}: {
  imports = [
    ../fish
    ../kitty
    ../git
    ../nvim
    ../ripgrep
    ../starship
  ];

  home.packages = with pkgs; [
    alejandra
    awscli
    bashInteractive
    bacon
    # brave
    coreutils
    curl
    erdtree
    fd
    ffmpeg
    flac
    gotop
    just
    lua
    # luajit
    less
    mas
    mpd
    mpc-cli
    nix-your-shell
    # opera
    ruby
    pandoc
    sketchybar
    tree-sitter
    xsv
    yazi
    youtube-dl
  ];

  # writes settings to the wrong location for macOS (~/.config vs Library/Application Support)
  # programs.bacon = {
  #   enable = true;
  # };
  programs.bash = {
    enable = true;
  };
  programs.bat = {
    enable = true;
    config = {
      theme = "base16-256";
    };
  };
  # programs.cava = {
  #   enable = true;
  #   settings = {};
  # };
  programs.fzf = {
    enable = true;
    enableFishIntegration = true;
  };
  programs.jq = {
    enable = true;
  };
  programs.lsd = {
    enable = true;
  };
  programs.ncmpcpp = {
    enable = true;
  };
  # programs.vscode = {
  #   enable = false;
  # };
  programs.zoxide = {
    enable = true;
  };
  programs.zsh = {
    enable = true;
  };
}
