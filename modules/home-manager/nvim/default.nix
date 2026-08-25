{
  lib,
  pkgs,
  ...
}: let
  managedTheme = import ../managed-theme.nix {inherit lib;};
  generatedTheme = pkgs.writeText "managed.lua" managedTheme.neovimThemeLua;
  nvimEditor = pkgs.writeShellScriptBin "nvim-editor" ''
    export NVIM_APPNAME=nvim-editor
    exec nvim "$@"
  '';
  luaConfig = pkgs.runCommand "nvim-lua-config" {} ''
    cp -R ${./lua} "$out"
    chmod -R u+w "$out"
    rm -rf "$out/theme"
    mkdir -p "$out/theme"
    cp ${generatedTheme} "$out/theme/managed.lua"
  '';
in {
  home.packages = [nvimEditor];

  home.activation.nvimEditorProfileMigration = lib.hm.dag.entryBefore ["checkLinkTargets"] ''
    if [ -L "$HOME/.config/nvim-editor" ]; then
      case "$(readlink "$HOME/.config/nvim-editor")" in
        *-home-manager-files/.config/nvim-editor) rm "$HOME/.config/nvim-editor" ;;
      esac
    fi
  '';

  programs.neovim = {
    enable = false;
    withNodeJs = false;
    withRuby = false;
    viAlias = true;
    vimAlias = true;
    vimdiffAlias = true;
  };

  xdg.configFile."nvim-editor/after/ftplugin/gitcommit.lua".source = ./after/ftplugin/gitcommit.lua;
  xdg.configFile."nvim-editor/after/ftplugin/markdown.lua".source = ./editor/after/ftplugin/markdown.lua;
  xdg.configFile."nvim-editor/init.lua".source = ./editor/init.lua;
  xdg.configFile."nvim-editor/lua/theme/managed.lua".source = generatedTheme;
  xdg.configFile."nvim-editor/syntax/pi.vim".source = ./editor/syntax/pi.vim;
  xdg.configFile."nvim/after".source = ./after;
  xdg.configFile."nvim/AGENTS.md".source = ./AGENTS.md;
  xdg.configFile."nvim/init.lua".source = ./init.lua;
  xdg.configFile."nvim/lsp".source = ./lsp;
  xdg.configFile."nvim/lua".source = luaConfig;
  # xdg.configFile."nvim/plugin".source = ./plugin;
  xdg.configFile."nvim/syntax".source = ./syntax;
}
