{
  config,
  lib,
  pkgs,
  ...
}: let
  # A headless "VNC" output keeps sharing available while physical monitors
  # sleep (some DisplayPort monitors disconnect on DPMS off). Omarchy's own
  # hyprctl talks to the running session; create the output only if missing.
  ensureOutput = pkgs.writeShellScript "wayvnc-ensure-output" ''
    set -eu
    if ! /usr/bin/hyprctl monitors all -j | ${lib.getExe pkgs.jq} -e 'any(.[]; .name == "VNC")' >/dev/null; then
      /usr/bin/hyprctl output create headless VNC
    fi
  '';
in {
  options.omarchyVnc.address = lib.mkOption {
    type = lib.types.str;
    example = "100.97.112.40";
    description = "This host's stable Tailscale IPv4 address; the only VNC listener.";
  };

  config = {
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
          ExecStartPre = "${ensureOutput}";
          ExecStart = "${lib.getExe pkgs.wayvnc} --config=%h/.config/wayvnc/config --output=VNC ${config.omarchyVnc.address}";
          # wayvnc exits 0 when its output disappears; restart regardless.
          Restart = "always";
          RestartSec = 3;
          UMask = "0077";
          NoNewPrivileges = true;
        };

        Install.WantedBy = ["graphical-session.target"];
      };
    };
  };
}
