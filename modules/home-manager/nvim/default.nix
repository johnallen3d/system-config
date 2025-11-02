{...}: {
  programs.neovim = {
    enable = false;
    withNodeJs = false;
    withRuby = false;
    viAlias = true;
    vimAlias = true;
    vimdiffAlias = true;
  };

  xdg.configFile."nvim/after".source = ./after;
  xdg.configFile."nvim/AGENTS.md".source = ./AGENTS.md;
  xdg.configFile."nvim/init.lua".source = ./init.lua;
  xdg.configFile."nvim/lsp".source = ./lsp;
  xdg.configFile."nvim/lua".source = ./lua;
  # xdg.configFile."nvim/plugin".source = ./plugin;
  xdg.configFile."nvim/syntax".source = ./syntax;
}
