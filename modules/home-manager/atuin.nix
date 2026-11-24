_: {
  # Local-only shell history. fish binds Ctrl+R to Atuin (replacing tv's history
  # search); zsh and bash keep their own Ctrl+R, since tv never handled it there.
  # Up stays with the shell, and `?` is not bound to hosted Atuin AI.
  # The daemon and agent thread capture stay off.
  programs.atuin = {
    enable = true;
    flags = ["--disable-up-arrow" "--disable-ai" "--disable-ctrl-r"];
    settings = {
      auto_sync = false;
      update_check = false;
    };
  };
}
