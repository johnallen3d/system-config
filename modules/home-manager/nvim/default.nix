{
  lib,
  pkgs,
  ...
}: let
  tokyoNight = import ../tokyo-night.nix {inherit lib;};
  generatedTheme = pkgs.writeText "tokyo_night_moon.lua" tokyoNight.nvimLua;
  luaConfig = pkgs.runCommand "nvim-lua-config" {} ''
    cp -R ${./lua} "$out"
    chmod -R u+w "$out"
    mkdir -p "$out/theme/generated"
    cp ${generatedTheme} "$out/theme/generated/tokyo_night_moon.lua"
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
  xdg.configFile."nvim/colors".source = ./colors;
  xdg.configFile."nvim/init.lua".source = ./init.lua;
  xdg.configFile."nvim/lsp".source = ./lsp;
  xdg.configFile."nvim/lua".source = luaConfig;
  # xdg.configFile."nvim/plugin".source = ./plugin;
  xdg.configFile."nvim/syntax".source = ./syntax;
}
