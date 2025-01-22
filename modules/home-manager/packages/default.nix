{
  pkgs,
  rip2,
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
      # awscli2
      # azure-cli
      bashInteractive
      bacon
      # brave
      cargo-careful
      cargo-machete
      cargo-nextest
      cargo-sweep
      coreutils
      curl
      devbox
      doctl
      # dotnet-runtime -> this is included in the dotnet-sdk
      # dotnet-sdk -> trying to install this via homebrew for better tools support
      duckdb
      entr
      fd
      ffmpeg
      findutils # find / xargs
      flac
      flyctl
      fswatch
      gawk
      go
      glow
      gnugrep
      gotop
      home-manager
      hurl
      just
      k3d
      k9s
      # not currently supported on ARM architecture
      # installed via: curl -fsSL https://kcl-lang.io/script/install-cli.sh | /bin/bash
      # https://www.kcl-lang.io/docs/user_docs/getting-started/install#using-script-to-install-the-latest-release
      # kcl-cli
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
      mpd
      # mpc-cli
      nix-your-shell
      nodejs_22
      oras
      rip2.packages.${pkgs.system}.default
      ruby
      pandoc
      postgresql
      # pyenv
      python312Packages.mkdocs-material
      qmk
      sqlite
      tailscale
      tree-sitter
      uv
      vals
      viddy
      yq-go
      wget
      xc
      xsv
      yazi
      # youtube-dl
      yt-dlp
      zellij
    ]
    ++ scripts;

  programs.atuin = {
    enable = true;
    flags = [
      "--disable-up-arrow"
    ];
    settings = {
      keymap_mode = "emacs";
      show_help = false;
      show_preview = true;
      style = "compact";
      update_check = false;
    };
  };
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
