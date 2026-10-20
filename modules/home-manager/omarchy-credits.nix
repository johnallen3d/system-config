# Host-local service: deliberately listen on Omarchy's physical LAN, not Tailscale.
{
  config,
  credits,
  lib,
  pkgs,
  ...
}: let
  state = "${config.xdg.stateHome}/credits";
  package = import ./packages/credits.nix {
    inherit pkgs;
    src = credits;
  };
  lanAddress = "192.168.4.26";
in {
  home.packages = [package];

  home.activation.creditsState = lib.hm.dag.entryAfter ["writeBoundary"] ''
    $DRY_RUN_CMD ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArg state}
  '';

  systemd.user.services = {
    credits = {
      Unit = {
        Description = "Credits movie and TV browser (loopback backend)";
        StartLimitIntervalSec = 0;
      };
      Service = {
        ExecStart = "${lib.getExe pkgs.doppler} run --no-read-env --no-check-version --project credits --config dev --preserve-env=CREDITS_BIND,CREDITS_DB --fallback=${state}/doppler-fallback.json -- ${lib.getExe package}";
        Environment = [
          "CREDITS_BIND=127.0.0.1:3001"
          "CREDITS_DB=${state}/cache.sqlite3"
        ];
        WorkingDirectory = state;
        Restart = "always";
        RestartSec = 5;
        TimeoutStopSec = 30;
        UMask = "0077";
        NoNewPrivileges = true;
      };
      Install.WantedBy = ["default.target"];
    };

    credits-lan = {
      Unit.Description = "LAN-only TCP proxy for Credits";
      Service = {
        ExecStart = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd 127.0.0.1:3001";
        NoNewPrivileges = true;
      };
    };
  };

  systemd.user.sockets.credits-lan = {
    Unit.Description = "Credits on ${lanAddress}:3000 (not the Tailscale interface)";
    Socket = {
      ListenStream = "${lanAddress}:3000";
      FreeBind = true;
      NoDelay = true;
    };
    Install.WantedBy = ["sockets.target"];
  };
}
