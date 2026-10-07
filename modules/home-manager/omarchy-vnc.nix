{
  lib,
  pkgs,
  ...
}: {
  # Home Manager otherwise adds a generic tray target when systemd is enabled.
  # Leave unrelated desktop/session units under Omarchy's ownership.
  xdg.configFile."systemd/user/tray.target".enable = false;

  systemd.user = {
    enable = true;
    startServices = "sd-switch";
    systemctlPath = "/usr/bin/systemctl";

    # UWSM/Omarchy owns the GUI environment; only manage this service.
    sessionVariables = lib.mkForce {};

    services.wayvnc = {
      Unit = {
        Description = "Omarchy desktop sharing over Tailscale-only VNC";
        Documentation = ["man:wayvnc(1)"];
        After = ["graphical-session.target"];
        Requisite = ["graphical-session.target"];
        PartOf = ["graphical-session.target"];
        ConditionPathExists = "%h/.config/wayvnc/config";
        # Retry if Tailscale's address is not ready when the GUI starts.
        StartLimitIntervalSec = 0;
      };

      Service = {
        # Preserve the existing private password file outside the Nix store.
        # Override the file's bind address with this host's verified tailnet IP.
        # Never expose the listener on the LAN or all interfaces.
        ExecStart = "${lib.getExe pkgs.wayvnc} --config=%h/.config/wayvnc/config 100.97.112.40";
        Restart = "on-failure";
        RestartSec = 3;
        UMask = "0077";
        NoNewPrivileges = true;
      };

      Install.WantedBy = ["graphical-session.target"];
    };
  };
}
