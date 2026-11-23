# The 05:00 morning brief: the notes vault's own task, run as John. It uses
# John's gog tokens and his Doppler login (notes/prd for the gog keyring
# password, notes/pocket for the Telegram bot).
{
  config,
  lib,
  pkgs,
  ...
}: let
  notes = "${config.home.homeDirectory}/notes";
  path = lib.makeBinPath [
    (import ./packages/vlt.nix {inherit pkgs;})
    pkgs.bash
    pkgs.coreutils
    pkgs.doppler
    pkgs.gogcli
    pkgs.python3
  ];
in {
  systemd.user.services.morning-brief = {
    Unit.Description = "Morning brief into today's daily note";
    Service = {
      Type = "oneshot";
      ExecStart = "${notes}/.mise/tasks/morning-brief";
      WorkingDirectory = notes;
      Environment = [
        "PATH=${path}"
        "TZ=America/New_York"
        "VAULT_DIR=${notes}"
        # No Obsidian app config here, so vlt can't find the vault by name.
        "VLT_VAULT_PATH=${notes}"
        "GOG_KEYRING_BACKEND=file"
        "GOG_TIMEZONE=America/New_York"
      ];
      UMask = "0077";
      NoNewPrivileges = true;
    };
  };

  systemd.user.timers.morning-brief = {
    Unit.Description = "Daily morning brief at 05:00";
    Timer = {
      OnCalendar = "*-*-* 05:00:00";
      Persistent = true;
    };
    Install.WantedBy = ["timers.target"];
  };
}
