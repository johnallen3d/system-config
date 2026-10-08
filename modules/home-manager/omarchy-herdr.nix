{
  config,
  lib,
  pkgs,
  ...
}: let
  homeDir = config.home.homeDirectory;
  # Add Worktrunk's cd function only inside Herdr. Do not edit Omarchy's
  # .bashrc or install shell integration into user-owned startup files.
  paneRc = pkgs.writeText "herdr-omarchy-bashrc" ''
    if [ -r "$HOME/.bashrc" ]; then source "$HOME/.bashrc"; fi
    export PATH="$HOME/.local/bin:$HOME/.nix-profile/bin:$PATH"
    eval "$(${pkgs.worktrunk}/bin/wt config shell init bash)"
  '';
  paneShell = pkgs.writeShellScript "herdr-omarchy-shell" (
    if config.programs.fish.enable
    then ''exec ${lib.getExe config.programs.fish.package} "$@"''
    else ''exec /usr/bin/bash --rcfile ${paneRc} "$@"''
  );
  launchers = {
    herdr = pkgs.herdr;
    herdr-open-wt = import ./packages/bin/herdr-open-wt.nix {inherit pkgs;};
  };
in {
  imports = [./herdr.nix];

  # Keep the isolated host independent of the shared shell/desktop modules.
  home.packages = with pkgs; [fzf herdr worktrunk] ++ [launchers.herdr-open-wt];
  home.file = lib.mapAttrs' (name: package:
    lib.nameValuePair ".local/bin/${name}" {source = "${package}/bin/${name}";})
  launchers;

  # Adopt the reviewed pre-existing Linux configuration, not the Mac's cmd keys.
  xdg.configFile."herdr/config.toml".text =
    lib.replaceStrings
    ["[terminal]"]
    ["[terminal]\ndefault_shell = \"${paneShell}\""]
    (builtins.readFile ./dotfiles/config/herdr/omarchy.toml);
  home.activation.herdrConfigMigration = lib.hm.dag.entryBefore ["writeBoundary"] ''
    path="${homeDir}/.config/herdr/config.toml"
    if [ -f "$path" ] && [ ! -L "$path" ]; then
      if ${pkgs.diffutils}/bin/cmp -s "$path" ${./dotfiles/config/herdr/omarchy.toml}; then
        backup="${homeDir}/.cache/herdr/pre-home-manager-config.toml"
        if [ -e "$backup" ]; then
          echo "Refusing to overwrite Herdr configuration backup: $backup" >&2
          exit 1
        fi
        $DRY_RUN_CMD mkdir -p "${homeDir}/.cache/herdr"
        $DRY_RUN_CMD mv "$path" "$backup"
      else
        echo "Refusing to replace modified Herdr configuration: $path" >&2
        exit 1
      fi
    fi
  '';

  systemd.user.services.herdr = {
    Unit = {
      Description = "Persistent Herdr coding-agent session";
      Documentation = ["https://herdr.dev/docs/"];
      # Applying a package/unit update must not kill active agents. Restart
      # explicitly once work is finished to use a new server binary.
      X-RestartIfChanged = false;
      X-StopIfChanged = false;
    };
    Service = {
      Type = "simple";
      ExecStart = "${lib.getExe pkgs.herdr} --session default server";
      WorkingDirectory = homeDir;
      Environment = [
        "PATH=${homeDir}/.local/bin:${homeDir}/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin"
        "SHELL=/usr/bin/bash"
        "PI_CODING_AGENT_DIR=${homeDir}/.config/pi"
        "CLAUDE_CONFIG_DIR=${homeDir}/.config/claude-personal"
      ];
      Restart = "on-failure";
      RestartSec = 3;
      UMask = "0077";
    };
    Install.WantedBy = ["default.target"];
  };
}
