{
  pkgs,
  op_path,
  ...
}: let
  scripts = [
    (import ./bin/chat-gpt-key.nix {
      inherit pkgs;
      inherit op_path;
    })
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
    ../alacritty
    ../direnv
    ../fish
    ../git
    ../nvim
    ../ripgrep
    ../starship
  ];

  home.packages = with pkgs;
    [
      alejandra
      argo
      argocd
      awscli2
      # azure-cli
      bashInteractive
      bacon
      # brave
      bun
      cargo-careful
      cargo-machete
      cargo-nextest
      cargo-sweep
      coreutils
      curl
      devbox
      docker-client
      doctl
      # dotnet-runtime -> this is included in the dotnet-sdk
      # dotnet-sdk -> trying to install this via homebrew for better tools support
      # duckdb
      entr
      fd
      ffmpeg
      findutils # find / xargs
      flac
      flyctl
      fswatch
      gawk
      google-cloud-sdk
      go
      glow
      gnugrep
      gotop
      home-manager
      # hurl
      imagemagick
      just
      k3d
      k9s
      kcl
      kind
      kubecolor
      kubectl
      kubernetes-helm
      kubeseal
      kubie
      # TODO: for some reason using this version of Lua causes issues with SbarLua
      # lua
      # luajit
      less
      minikube
      minio-client
      mkdocs
      # mpd
      # mpc-cli
      nix-your-shell
      nodejs_24
      oras
      # TODO: "marked as broken"
      # release-plz
      ruby
      pandoc
      postgresql
      qmk
      qsv
      skim # fzf alternative
      sqlite
      tree-sitter
      uv
      vals
      viddy
      yq-go
      wget
      xc
      yazi
      # youtube-dl
      yt-dlp
      # slightly outdated
      # zed-editor
      zellij
    ]
    ++ scripts;

  # writes settings to the wrong location for macOS (~/.config vs Library/Application Support)
  # programs.bacon = {
  #   enable = true;
  # };
  programs.bash = {
    enable = true;

    profileExtra = ''
      if [ -e ~/.nix-profile/etc/profile.d/nix.sh ]; then
        . ~/.nix-profile/etc/profile.d/nix.sh
      fi
      export PATH=$HOME/.nix-profile/bin:$PATH
    '';
    initExtra = ''
      if [ -e "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh" ]; then
        . "$HOME/.nix-profile/etc/profile.d/hm-session-vars.sh"
      fi
    '';
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
  programs.jq = {
    enable = true;
  };
  programs.lsd = {
    enable = true;
  };
  # programs.ncmpcpp = {
  #   enable = true;
  # };
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
