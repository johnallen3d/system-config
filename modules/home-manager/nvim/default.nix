{...}: {
  programs.neovim = {
    enable = true;
    withNodeJs = false;
    withRuby = false;
    viAlias = true;
    vimAlias = true;
    vimdiffAlias = true;
  };

  xdg.configFile."nvim/lazyvim.json".source = ./lazyvim.json;
  xdg.configFile."nvim/lua".source = ./lua;
}
