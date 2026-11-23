# Omarchy-only Forkful food-logging PWA. The vault on this host is the data
# owner; Omarchy centralizes writes so phones never create Syncthing conflicts.
# pi-01 Caddy serves it at https://forkful.jallen7usa.com through a LAN-only
# forwarder (private DNS, never the tunnel: there is no app authentication).
# Native UFW must allow pi-01 to lanAddress:lanPort:
#   sudo ufw allow in on enp3s0 proto tcp from 192.168.5.11 to 192.168.4.26 port 4410 comment 'forkful from pi-01 only'
{
  config,
  forkful,
  lib,
  pkgs,
  ...
}: let
  package = forkful.packages.${pkgs.stdenv.hostPlatform.system}.default;
  port = 4411;
  lanPort = 4410;
  # Omarchy's reserved physical LAN address, never the Tailscale interface.
  lanAddress = "192.168.4.26";
in {
  systemd.user.services = {
    forkful = {
      Unit = {
        Description = "Forkful food-logging PWA (loopback backend)";
        StartLimitIntervalSec = 0;
      };
      Service = {
        ExecStart = lib.getExe package;
        Environment = [
          "FORKFUL_BIND=127.0.0.1:${toString port}"
          "VAULT_DIR=${config.home.homeDirectory}/notes"
        ];
        WorkingDirectory = "${config.home.homeDirectory}/notes";
        Restart = "always";
        RestartSec = 5;
        NoNewPrivileges = true;
      };
      Install.WantedBy = ["default.target"];
    };

    forkful-lan = {
      Unit.Description = "LAN-only TCP proxy for Forkful";
      Service = {
        ExecStart = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd 127.0.0.1:${toString port}";
        NoNewPrivileges = true;
      };
    };
  };

  systemd.user.sockets.forkful-lan = {
    Unit.Description = "Forkful on ${lanAddress}:${toString lanPort} (not the Tailscale interface)";
    Socket = {
      ListenStream = "${lanAddress}:${toString lanPort}";
      FreeBind = true;
      NoDelay = true;
    };
    Install.WantedBy = ["sockets.target"];
  };
}
