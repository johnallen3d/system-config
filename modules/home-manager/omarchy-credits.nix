# Host-local service: deliberately listen on Omarchy's physical LAN, not Tailscale.
{
  config,
  lib,
  pkgs,
  ...
}: let
  state = "${config.xdg.stateHome}/credits";
  lanAddress = "192.168.4.26";
  runtimePath = lib.makeBinPath [
    pkgs.coreutils
    pkgs.git
    pkgs.mise
    pkgs.openssh
    pkgs.pkg-config
    pkgs.stdenv.cc
    pkgs.systemd
  ];
  updater = pkgs.writeShellScriptBin "credits-update" ''
    export PATH=${lib.escapeShellArg runtimePath}
    export CREDITS_STATE=${lib.escapeShellArg state}
    export CREDITS_REPOSITORY=https://github.com/johnallen3d/credits.git
    export GIT_TERMINAL_PROMPT=0
    exec ${lib.getExe pkgs.python3} ${./credits-service/update.py} "$@"
  '';
  server = pkgs.writeShellScript "credits-server" ''
    umask 077
    cd ${lib.escapeShellArg state}
    export CREDITS_BIND=127.0.0.1:3001
    export CREDITS_DB=${lib.escapeShellArg "${state}/cache.sqlite3"}
    exec ${lib.getExe pkgs.doppler} run --no-read-env --no-check-version \
      --project credits --config dev \
      --preserve-env=CREDITS_BIND,CREDITS_DB \
      --fallback=${lib.escapeShellArg "${state}/doppler-fallback.json"} \
      -- ${lib.escapeShellArg "${state}/current/credits"}
  '';
in {
  home.packages = [updater];

  home.activation.creditsState = lib.hm.dag.entryAfter ["writeBoundary"] ''
    $DRY_RUN_CMD ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArg state}
  '';

  systemd.user.services = {
    credits = {
      Unit = {
        Description = "Credits movie and TV browser (loopback backend)";
        ConditionFileIsExecutable = "${state}/current/credits";
        StartLimitIntervalSec = 0;
      };
      Service = {
        ExecStart = server;
        WorkingDirectory = state;
        Restart = "always";
        RestartSec = 5;
        TimeoutStopSec = 30;
        UMask = "0077";
        NoNewPrivileges = true;
      };
      Install.WantedBy = ["default.target"];
    };

    credits-update = {
      Unit.Description = "Build, test and deploy Credits from GitHub main";
      Service = {
        Type = "oneshot";
        ExecStart = "${updater}/bin/credits-update";
        WorkingDirectory = state;
        TimeoutStartSec = "50min";
        UMask = "0077";
        Nice = 10;
        NoNewPrivileges = true;
      };
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

  systemd.user.timers.credits-update = {
    Unit.Description = "Check GitHub main for Credits updates every five minutes";
    Timer = {
      OnActiveSec = "15s";
      OnUnitInactiveSec = "5min";
      Persistent = true;
      Unit = "credits-update.service";
    };
    Install.WantedBy = ["timers.target"];
  };
}
