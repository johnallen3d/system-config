{pkgs, ...}: let
  shellAliases = {
    ":e" = "nvim";
    ":q" = "exit";
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
    ip = "ipconfig getifaddr en0";
    j = "z";
    k = "kubecolor";
    lazy = "cd ~/dev/src/system-config/modules/home-manager/nvim && nvim ./lua/plugins/init.lua";
    music = "ncmpcpp";
    nix-build = "darwin-rebuild switch --flake ~/dev/src/system-config/.#";
    notes = "cd ~/notes && nvim mindfulness/practice.md";
    pass = "passgen";
    passgen = "dd if=/dev/urandom bs=1 count=32 2>/dev/null | base64 | rev | cut -b 2- | rev";
    password = "passgen";
    recent = "lsd -la --sort time --color=always | head";
    rm = "echo Use 'rip' instead of rm";
    spp = "git stash && git pull && git stash pop";
    tree = "lsd --tree";
    uuid = "uuidgen | tr -d \\n | tr [:upper:] [:lower:] | pbcopy; pbpaste; echo";
    vi = "nvim";
    vim = "nvim";
    weather = "curl wttr.in";
    whatismyip = "curl -4 ifconfig.co/";
    yt = "youtube-dl -f bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best";
  };

  commonVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    GIT_EDITOR = "nvim";
    TIME_STYLE = "long-iso";
    MANPAGER = "nvim +Man!";
    FZF_DEFAULT_COMMAND = "rg --files --hidden --follow --glob \"!doc/*\"";
    PYENV_ROOT = "$HOME/.pyenv";
  };

  commonShells = with pkgs; [
    bash
    fish
    zsh
  ];
in {
  inherit shellAliases commonVariables commonShells;
}
