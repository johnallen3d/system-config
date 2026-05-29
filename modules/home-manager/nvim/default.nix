{
  lib,
  pkgs,
  ...
}: let
  managedTheme = import ../managed-theme.nix {inherit lib;};
  generatedThemes = lib.mapAttrs (variant: lua:
    pkgs.writeText "${managedTheme.nvimModuleName variant}.lua" lua) managedTheme.nvimLuaModules;
  luaConfig = pkgs.runCommand "nvim-lua-config" {} ''
    cp -R ${./lua} "$out"
    chmod -R u+w "$out"
    mkdir -p "$out/theme/generated"
${lib.concatMapStringsSep "\n" (variant: "    cp ${generatedThemes.${variant}} \"$out/theme/generated/${managedTheme.nvimModuleName variant}.lua\"") managedTheme.variantNames}
    cp ${generatedThemes.${managedTheme.activeVariant}} "$out/theme/generated/active.lua"
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
