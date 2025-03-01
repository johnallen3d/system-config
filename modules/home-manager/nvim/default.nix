{...}: {
  programs.neovim = {
    enable = true;
    withNodeJs = false;
    withRuby = false;
    viAlias = true;
    vimAlias = true;
    vimdiffAlias = true;
  };

  # Normal LazyVim config here, see https://github.com/LazyVim/starter/tree/main/lua
  xdg.configFile."nvim/legacy.vim".source = ./legacy.vim;
  xdg.configFile."nvim/lazyvim.json".source = ./lazyvim.json;
  xdg.configFile."nvim/lua".source = ./lua;
}
