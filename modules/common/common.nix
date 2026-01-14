{pkgs, ...}: let
  shellAliases = {
    ":e" = "nvim";
    ":q" = "exit";
    assume = "source /opt/homebrew/bin/assume.fish";
    dadbod = "nvim +DBUI";
    db = "delete-branch";
    downloads = "cd ~/Downloads";
    files = "yazi";
    gb = "git bv";
    gc = "git commit -v";
    gco = "git checkout";
    ghostty = "/Applications/Ghostty.app/Contents/MacOS/ghostty";
    gl = "git pull";
    gp = "git push";
    gpf = "git push --force-with-lease";
    gst = "git status --short";
    icat = "viu";
    j = "z";
    k = "kubecolor";
    notes = "cd ~/notes && nvim mindfulness/practice.md";
    pass = "passgen";
    passgen = "dd if=/dev/urandom bs=1 count=32 2>/dev/null | base64 | rev | cut -b 2- | rev";
    password = "passgen";
    recent = "lsd -la --sort time --color=always | head";
    spp = "git stash && git pull && git stash pop";
    tree = "lsd --tree";
    # tw = "tw --theme tokyo-night ";
    # can't ever remember the name of this command (`tw`), maybe this will stick? 🤷‍♂️
    tab = "tw ";
    par = "tw ";
    parquet = "tw ";
    uuid = "uuidgen | tr -d \\n | tr [:upper:] [:lower:] | pbcopy; pbpaste; echo";
    vi = "nvim";
    vim = "nvim";
    vi-sk = "nvim (sk)";
    weather = "curl wttr.in";
    whatismyip = "curl -4 ifconfig.co/";
    yt = "youtube-dl -f bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best";
  };

  commonVariables = {
    EDITOR = "nvim";
    GIT_EDITOR = "nvim";
    VISUAL = "nvim";

    LEADR_CONFIG_DIR = "$HOME/.config/leadr/";
    MANPAGER = "nvim +Man!";
    PYENV_ROOT = "$HOME/.pyenv";
    SKIM_DEFAULT_COMMAND = "fd --type f || git ls-tree -r --name-only HEAD || rg --files || find .";
    TIME_STYLE = "long-iso";
    # NOTE: this is meant as a macOS only workaround
    # see https://github.com/ghostty-org/ghostty/discussions/2832
    XDG_DATA_DIRS = ["/Applications/Ghostty.app/Contents/Resources/ghostty/shell-integration"];
  };

  commonShells = with pkgs; [
    bash
    fish
    zsh
  ];
in {
  inherit shellAliases commonVariables commonShells;
}
