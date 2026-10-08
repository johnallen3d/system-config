{
  config,
  pkgs,
  ...
}: let
  common = import ../common/common.nix {inherit pkgs;};
in {
  imports = [
    ./fish
    ./packages/omarchy-fish.nix
    ./starship
  ];

  programs.fish = {
    shellAliases = common.shellAliases;
    shellInit = ''
      set -gx SHELL ${config.home.homeDirectory}/.nix-profile/bin/fish

      # Fish does not source /etc/profile. Initialize Nix without the daemon
      # script's early `exit` terminating an already-initialized shell.
      if test -z "$__ETC_PROFILE_NIX_SOURCED"; and test -r /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
        source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.fish
      end

      # Reuse Omarchy's native bootstrap rather than translating or duplicating
      # its Bash code. Import only these two variables; keep agent profiles.
      if test -r /usr/share/omarchy/default/bash/env-bootstrap
        set -l omarchy_env (/usr/bin/bash --noprofile --norc -c '
          source /usr/share/omarchy/default/bash/env-bootstrap
          printf "%s\\0%s\\0" "$OMARCHY_PATH" "$PATH"
        ' | string split0)
        if test (count $omarchy_env) -eq 2
          set -gx OMARCHY_PATH $omarchy_env[1]
          set -gx PATH (string split : -- "$omarchy_env[2]")
        end
      end

      # Ordinary SSH commands are noninteractive: they need managed tools too.
      fish_add_path --global --move --prepend /nix/var/nix/profiles/default/bin
      fish_add_path --global --move --prepend $HOME/.nix-profile/bin
      fish_add_path --global --move --prepend $HOME/.local/bin
    '';
  };

  # Leave Omarchy's Bash prompt and ~/.config/starship.toml untouched.
  programs.starship = {
    configPath = "${config.xdg.configHome}/fish/starship.toml";
    enableBashIntegration = false;
    enableZshIntegration = false;
  };

  # Use Omarchy's native mise and Neovim; do not replace their configuration.
  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    GIT_EDITOR = "nvim";
    PI_RESPONSE_FEEDBACK = "1";
    TIME_STYLE = "long-iso";
  };

  xdg.configFile = {
    "television/config.toml".source = ./dotfiles/config/television/config.toml;
    "television/cable/fish-history.toml".source = ./dotfiles/config/television/cable/fish-history.toml;
  };
}
