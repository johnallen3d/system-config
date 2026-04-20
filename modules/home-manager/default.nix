{pkgs, ...}: let
  common = import ../common/common.nix {inherit pkgs;};
  musicDir = common.commonVariables.MUSIC_DIR;
in {
  home.stateVersion = "24.05";

  imports = [
    ./packages
    ./pi-extensions.nix
    ./pi-settings.nix
  ];

  home.sessionVariables = {
    CLAUDE_CONFIG_DIR = "$HOME/.config/claude-personal";
    CLAUDE_CODE_DISABLE_1M_CONTEXT = "1";
  };

  home = {
    file = {
      ".ctags".source = ./dotfiles/ctags;
      ".irbrc".source = ./dotfiles/irbrc;
      ".pryrc".source = ./dotfiles/pryrc;
      ".sqliterc".source = ./dotfiles/sqliterc;

      ".config/gh-dash/config.yml".source = ./dotfiles/config/gh-dash/config.yml;
      ".config/stylua.toml".source = ./dotfiles/config/stylua.toml;
      ".config/claude-gmatter/keybindings.json".source = ./dotfiles/config/claude-personal/keybindings.json;

      ".config" = {
        recursive = true;
        source = ./dotfiles/config;
      };

      "bin" = {
        recursive = true;
        source = ./dotfiles/bin;
      };

      "bin/bottombar".source = "${pkgs.sketchybar}/bin/sketchybar";

      ".tabby-client/agent/config.toml".source = ./dotfiles/tabby.toml;

      "Library/Application Support/org.dystroy.bacon/prefs.toml".source = ./dotfiles/bacon-prefs.toml;

      ".config/mpv-queue/config.toml".text = ''
        # mpv-queue configuration

        music_directory = "${musicDir}"

        [favorites]
        caamp = "Caamp/Lavender Days"
        caleb = "Caleb Grenier/Sandy Friends"
        dave = "Dave Matthews & Tim Reynolds/Live At Luther College"
        gizz = "King Gizzard & The Lizard Wizard/Nonagon Infinity"
        gogo = "GoGo Penguin/Man Made Object"
        goose = "Goose/Alive and Well"
        hania = "Hania Rani/Ghosts"
        joseph = "JOSEPH/I'm Alone, No You're Not"
        khruangbin = "Khruangbin/A LA SALA"
        nin = "Nine Inch Nails/2014.08.07 Charlotte, PNC Music Pavilion"
        noah = "Noah Kahan/Cape Elizabeth"
        ray = "Ray LaMontagne/Ouroboros"
        sarah = "Sarah Jarosz/Blue Heron Suite"
        tool = "Tool/Undertow"
        trey = "Trey Anastasio/Lonely Trip"
        violent = "Violent Femmes/Violent Femmes"
      '';
    };
  };
}
