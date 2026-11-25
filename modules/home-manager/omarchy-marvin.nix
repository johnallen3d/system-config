# Omarchy-only Marvin food-logging PWA. The vault on this host is the data
# owner; Omarchy centralizes writes so phones never create Syncthing
# conflicts. pi-01 Caddy serves it at
# https://marvin.jallen7usa.com (forkful.jallen7usa.com permanently redirects)
# through a LAN-only forwarder (private DNS, never the tunnel: there is no app
# authentication). Native UFW must allow pi-01 to lanAddress:lanPort:
#   sudo ufw allow in on enp3s0 proto tcp from 192.168.5.11 to 192.168.4.26 port 4410 comment 'marvin from pi-01 only'
{
  config,
  marvin,
  lib,
  pkgs,
  ...
}: let
  packages = marvin.packages.${pkgs.stdenv.hostPlatform.system};
  package = packages.default;
  port = 4411;
  chatPort = 4412;
  chatState = "${config.xdg.stateHome}/marvin-chat";
  lanPort = 4410;
  # Omarchy's reserved physical LAN address, never the Tailscale interface.
  lanAddress = "192.168.4.26";
  # Vault tasks shell out to vlt from the Home Manager profile, which the user
  # manager's PATH lacks. Environment= can't extend PATH, so prepend here.
  start = pkgs.writeShellScript "marvin-start" ''
    export PATH="${config.home.profileDirectory}/bin''${PATH:+:$PATH}"
    exec ${lib.getExe package}
  '';
in {
  home.activation.marvinChatState = lib.hm.dag.entryAfter ["writeBoundary"] ''
    $DRY_RUN_CMD ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArg chatState}
  '';

  systemd.user.services = {
    marvin = {
      Unit = {
        Description = "Marvin food-logging PWA (loopback backend)";
        StartLimitIntervalSec = 0;
      };
      Service = {
        ExecStart = "${start}";
        Environment = [
          "MARVIN_BIND=127.0.0.1:${toString port}"
          "VAULT_DIR=${config.home.homeDirectory}/notes"
          "MARVIN_CHAT_URL=http://127.0.0.1:${toString chatPort}"
        ];
        WorkingDirectory = "${config.home.homeDirectory}/notes";
        Restart = "always";
        RestartSec = 5;
        NoNewPrivileges = true;
      };
      Install.WantedBy = ["default.target"];
    };

    # Food-logging chat agent (pi-durable). Loopback only, reached through
    # marvin's /api/chat proxy; its tools call marvin's HTTP API, so vault
    # writes stay on marvin's locked tasks. Only its OpenRouter key comes from
    # Doppler notes/prd, never John's interactive pi/claude profiles.
    marvin-chat = {
      Unit = {
        Description = "Marvin chat agent sidecar (loopback backend)";
        # Soft ordering only: each side tolerates the other being down.
        Wants = ["marvin.service" "agent-browser.service"];
        After = ["marvin.service" "agent-browser.service"];
        StartLimitIntervalSec = 0;
      };
      Service = {
        ExecStart = "${lib.getExe pkgs.doppler} run --no-read-env --no-check-version --project notes --config prd --only-secrets OPENROUTER_API_KEY --fallback=${chatState}/doppler-fallback.json -- ${lib.getExe packages.chat}";
        Environment = [
          "MARVIN_CHAT_BIND=127.0.0.1:${toString chatPort}"
          "MARVIN_URL=http://127.0.0.1:${toString port}"
          "MARVIN_CHAT_STATE=${chatState}"
          "EXECUTOR_URL=${config.executor.mcpUrl}"
          "MARVIN_BROWSER_CDP_URL=http://127.0.0.1:${toString config.omarchyVoxl.cdpPort}"
          "MARVIN_VOXL_URL=https://${config.omarchyVoxl.host}:${toString config.omarchyVoxl.port}/"
        ];
        WorkingDirectory = chatState;
        Restart = "always";
        RestartSec = 5;
        TimeoutStopSec = 30;
        UMask = "0077";
        NoNewPrivileges = true;
      };
      Install.WantedBy = ["default.target"];
    };

    marvin-lan = {
      Unit.Description = "LAN-only TCP proxy for Marvin";
      Service = {
        ExecStart = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd 127.0.0.1:${toString port}";
        NoNewPrivileges = true;
      };
    };
  };

  systemd.user.sockets.marvin-lan = {
    Unit.Description = "Marvin on ${lanAddress}:${toString lanPort} (not the Tailscale interface)";
    Socket = {
      ListenStream = "${lanAddress}:${toString lanPort}";
      FreeBind = true;
      NoDelay = true;
    };
    Install.WantedBy = ["sockets.target"];
  };
}
