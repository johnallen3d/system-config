{
  pkgs,
  user,
  home,
  brew_bin,
  nix_bin,
  ...
}: {
  # https://github.com/nix-community/home-manager/issues/4026
  users.users.${user} = {
    home = "${home}";
    shell = pkgs.fish;
  };

  programs.fish.enable = true;

  environment = {
    loginShell = pkgs.fish;

    shells = with pkgs; [
      bash
      fish
      zsh
    ];

    pathsToLink = ["/Applications"];

    # TODO: this is duplicated in the `home-manager` module, is there any
    # benefit to this being here (eg. available to services)? If so, how to
    # share this list?
    systemPath = [
      "${pkgs.path}"
      "${nix_bin}"
      "/usr/local/bin"
      "$HOME/bin"
      "$HOME/.local/bin"
      "$HOME/.cargo/bin"
      "/run/current-system/sw/bin"
      "${brew_bin}"
    ];

    variables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
      GIT_EDITOR = "nvim";
      TIME_STYLE = "long-iso";
      MANPAGER = "nvim +Man!";
      FZF_DEFAULT_COMMAND = "rg --files --hidden --follow --glob \"!doc/*\"";
    };

    shellAliases = {
      ":e" = "nvim";
      ":q" = "exit";
      chat = "cd ~/Dropbox/Notes/scratch && nvim chat.md";
      db = "delete-branch";
      downloads = "cd ~/Downloads";
      files = "yazi";
      gb = "git bv";
      gc = "git commit -v";
      gco = "git checkout";
      gl = "git pull";
      gp = "git push";
      gpf = "git push --force-with-lease";
      gst = "git status --short";
      icat = "kitty +kitten icat";
      j = "z";
      lazy = "cd ~/dev/src/system-config/modules/home-manager/nvim && nvim ./lua/plugins/init.lua";
      music = "ncmpcpp";
      nix-build = "darwin-rebuild switch --flake ~/dev/src/system-config/.#";
      notes = "cd ~/notes && nvim health/Mindfulness.md";
      pass = "passgen";
      passgen = "dd if=/dev/urandom bs=1 count=32 2>/dev/null | base64 | rev | cut -b 2- | rev";
      password = "passgen";
      pi = "kitty +kitten ssh pi@pi.local";
      recent = "lsd -la --sort time --color=always | head";
      spp = "git stash && git pull && git stash pop";
      tree = "erd";
      uuid = "uuidgen | tr -d \\n | tr [:upper:] [:lower:] | pbcopy; pbpaste; echo";
      vi = "nvim";
      vim = "nvim";
      weather = "curl wttr.in";
      yt = "youtube-dl -f bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best";
    };
  };
}
