{
  pkgs,
  op_path,
  ...
}: let
  scripts = [
    (import ./bin/bv.nix {inherit pkgs;})
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
  mpv-queue = import ./mpv-queue.nix {inherit pkgs;};
  nail-parquet = import ./nail-parquet.nix {inherit pkgs;};
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
      actionlint
      aichat
      alejandra
      awscli2
      # azure-cli
      bashInteractive
      bacon
      basedpyright
      # biome
      # brave
      bun
      cargo-careful
      chafa
      cargo-machete
      cargo-nextest
      cargo-sweep
      claude-code
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
      github-copilot-cli
      github-mcp-server
      google-cloud-sdk
      go
      glow
      gnugrep
      gotop
      harper
      home-manager
      # hurl
      imagemagick
      just
      k3d
      kitty
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
      lf
      # llm # broken in nixpkgs jan 2025 - test failures
      lua-language-server
      markdownlint-cli2
      # marksman # broken in nixpkgs oct 2025 - dotnet build takes forever
      minikube
      minio-client
      mkdocs
      mods
      nix-search-cli
      nix-your-shell
      nixd
      nodejs_24
      oras
      # TODO: "marked as broken"
      # release-plz
      ruby
      ruff
      pandoc
      poppler-utils
      postgresql
      prettier
      rainfrog
      # qmk
      qsv
      skim # fzf alternative
      socat
      sqlite
      # this is quite outdated and under active development
      # sqruff
      stylua
      tree-sitter
      uv
      vals
      viddy
      viu
      vsce
      vscode-langservers-extracted
      websocat
      wget
      xc
      yamlfmt
      # yazi
      # youtube-dl
      yq-go
      yt-dlp
      # slightly outdated
      # zed-editor
      zellij
    ]
    ++ scripts
    ++ [mpv-queue nail-parquet];

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
    # don't user default aliases; see modules/home-manager/fish/functions.nix
    enableFishIntegration = false;
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
