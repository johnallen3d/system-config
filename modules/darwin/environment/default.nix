{
  pkgs,
  user,
  home,
  brew_bin,
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

    systemPath = [
      "${pkgs.path}"
      "/usr/local/bin"
      "$HOME/bin"
      "$HOME/.local/bin"
      "$HOME/.cargo/bin"
      "${brew_bin}"
    ];

    variables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
      GIT_EDITOR = "nvim";
      TIME_STYLE = "long-iso";
      MANPAGER = "nvim +Man!";
      FZF_DEFAULT_COMMAND = "rg --files --hidden --follow --glob \"!doc/*\"";
      # TODO: can we find a better/more nix way?
      PYENV_ROOT = "$HOME/.pyenv";
    };

    shellAliases = {
      ":e" = "nvim";
      ":q" = "exit";
      db = "delete-branch";
      downloads = "cd ~/Downloads";
      files = "lf";
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
