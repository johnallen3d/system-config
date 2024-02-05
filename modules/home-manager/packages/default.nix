{pkgs, ...}: let
  scripts = [
    (import ./bin/chat-gpt-key.nix {inherit pkgs;})
    (import ./bin/csv-headers.nix {inherit pkgs;})
    (import ./bin/delete-branch.nix {inherit pkgs;})
    (import ./bin/find-and-replace.nix {inherit pkgs;})
    (import ./bin/fixup.nix {inherit pkgs;})
    (import ./bin/flac-to-mp3.nix {inherit pkgs;})
    (import ./bin/md-to-doc.nix {inherit pkgs;})
    (import ./bin/scratch.nix {inherit pkgs;})
    (import ./bin/set-wallpaper.nix {inherit pkgs;})
    (import ./bin/wav-to-mp3.nix {inherit pkgs;})
  ];
in {
  imports = [
    ../direnv
    ../fish
    ../git
    ../lf
    ../nvim
    ../ripgrep
    ../starship
  ];

  home.packages = with pkgs;
    [
      alejandra
      awscli
      bashInteractive
      bacon
      # brave
      cargo-sweep
      coreutils
      curl
      fd
      ffmpeg
      findutils # find / xargs
      flac
      gawk
      gnugrep
      gotop
      just
      lua
      # luajit
      less
      mpd
      mpc-cli
      nix-your-shell
      nodejs_21
      ruby
      pandoc
      pyenv
      sqlite
      tailscale
      tree-sitter
      wget
      xsv
      youtube-dl
    ]
    ++ scripts;

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
      theme = "tokyonight_night";
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
