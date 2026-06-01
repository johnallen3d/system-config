{
  lib,
  pkgs,
  ...
}: let
  managedTheme = import ../managed-theme.nix {inherit lib;};
  generatedTheme = pkgs.writeText "managed.lua" managedTheme.neovimThemeLua;
  luaConfig = pkgs.runCommand "nvim-lua-config" {} ''
    cp -R ${./lua} "$out"
    chmod -R u+w "$out"
    rm -rf "$out/theme"
    mkdir -p "$out/theme"
    cp ${generatedTheme} "$out/theme/managed.lua"
  '';
in {
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
  xdg.configFile."nvim/lua".source = luaConfig;
  # xdg.configFile."nvim/plugin".source = ./plugin;
  xdg.configFile."nvim/syntax".source = ./syntax;
}
