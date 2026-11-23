# Central personal Executor v2 self-host gateway (Omarchy singleton) and
# tailnet MCP client config, mirroring subscription-proxy.nix.
# Personal-only for now; ports 4402 / 4444 remain reserved for a future work instance.
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.executor;
  containerName = "executor-personal";
  volumeName = "executor-personal-data";
  backupDir = "${config.home.homeDirectory}/.local/share/executor/backups";

  # Arch's Docker Engine is a socket-activated system service; a user manager
  # started before docker group membership needs newgrp (same pattern as nod).
  docker = pkgs.writeShellScript "executor-docker" ''
    set -euo pipefail
    cmd=(/usr/bin/docker "$@")
    if id -nG | grep -qw docker; then exec "''${cmd[@]}"; fi
    SHELL=/bin/sh exec /usr/bin/newgrp docker -c "exec ''${cmd[*]@Q}"
  '';

  startServer = pkgs.writeShellScript "executor-personal-start" ''
    set -euo pipefail
    ${docker} rm -f ${containerName} >/dev/null 2>&1 || true
    if ! ${docker} image inspect ${lib.escapeShellArg cfg.image} >/dev/null 2>&1; then
      ${docker} pull ${lib.escapeShellArg cfg.image}
    fi
    exec ${docker} run --rm \
      --name ${containerName} \
      --init \
      -p 127.0.0.1:${toString cfg.port}:4400 \
      -v ${volumeName}:/app/data \
      -e BETTER_AUTH_URL=${lib.escapeShellArg cfg.origin} \
      -e EXECUTOR_ENVIRONMENT=personal \
      -e EXECUTOR_APPS_ALLOW_PRIVATE_FETCH=${lib.boolToString cfg.allowPrivateFetch} \
      -e EXECUTOR_APP_WORKERS=32 \
      -e EXECUTOR_MCP_CLIENTS=64 \
      -e EXECUTOR_MCP_CLIENTS_PER_USER=64 \
      -e EXECUTOR_NO_UPDATE_CHECK=1 \
      -e EXECUTOR_DISABLE_ANALYTICS=1 \
      ${lib.escapeShellArg cfg.image}
  '';

  stopServer = pkgs.writeShellScript "executor-personal-stop" ''
    set -euo pipefail
    ${docker} stop -t 30 ${containerName} >/dev/null 2>&1 || true
  '';

  ctl = pkgs.writeShellApplication {
    name = "executor-ctl";
    runtimeInputs = [pkgs.curl pkgs.coreutils];
    text = ''
      set -euo pipefail
      origin=${lib.escapeShellArg cfg.origin}
      cmd="''${1:-ui}"
      case "$cmd" in
        ui)
          echo "Executor personal dashboard: $origin"
          if [ "$(uname -s)" = Darwin ]; then
            /usr/bin/open "$origin"
          elif [ -n "''${DISPLAY:-}''${WAYLAND_DISPLAY:-}" ] && command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$origin" >/dev/null 2>&1 &
          fi
          ;;
        status)
          code="$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' --max-time 5 "$origin/health" || echo 000)"
          echo "Endpoint: $origin/health (HTTP $code)"
          ${lib.optionalString cfg.server.enable ''
            echo "Service:  $(${pkgs.systemd}/bin/systemctl --user is-active executor-personal.service || true)"
            ${docker} ps -a --filter "name=^/${containerName}$" --format 'Container: {{.Names}} ({{.Status}}, {{.Image}})' || true
          ''}
          [ "$code" = 200 ]
          ;;
        ${lib.optionalString cfg.server.enable ''
        backup)
          dest="''${2:-${backupDir}}"
          mkdir -p "$dest"
          chmod 0700 "$dest"
          stamp="$(date +%Y%m%d-%H%M%S)"
          archive="executor-personal-data-$stamp.tar.gz"
          was_active=0
          if ${pkgs.systemd}/bin/systemctl --user is-active --quiet executor-personal.service; then
            was_active=1
            ${pkgs.systemd}/bin/systemctl --user stop executor-personal.service
          fi
          trap 'if [ "$was_active" = 1 ]; then ${pkgs.systemd}/bin/systemctl --user start executor-personal.service; fi' EXIT
          ${docker} run --rm \
            -v ${volumeName}:/data:ro \
            -v "$dest:/backup" \
            alpine:3.21 tar czf "/backup/$archive" -C /data .
          chmod 0600 "$dest/$archive"
          echo "Backed up ${volumeName} to $dest/$archive"
          ;;
        ''}
        *)
          echo "Usage: executor-ctl [ui|status${lib.optionalString cfg.server.enable "|backup [dir]"}]" >&2
          exit 2
          ;;
      esac
    '';
  };
in {
  options.executor = {
    enable = lib.mkEnableOption "central personal Executor v2 MCP client wiring and dashboard helper";
    server.enable = lib.mkEnableOption "the Omarchy personal Executor v2 self-host Docker service";
    origin = lib.mkOption {
      type = lib.types.str;
      default = "https://omarchy.taila14c2.ts.net:4443";
      description = "Tailnet-only HTTPS origin served by Tailscale Serve (must match BETTER_AUTH_URL).";
    };
    mcpUrl = lib.mkOption {
      type = lib.types.str;
      default = "${cfg.origin}/mcp";
      description = "Streamable HTTP MCP endpoint for personal Executor clients.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 4401;
      description = "Loopback port bound on Omarchy for the personal Executor container.";
    };
    httpsPort = lib.mkOption {
      type = lib.types.port;
      default = 4443;
      description = "Tailscale Serve HTTPS port exposing the personal Executor container on the tailnet.";
    };
    image = lib.mkOption {
      type = lib.types.str;
      default = "ghcr.io/usefulsoftwareco/executor-selfhost:2.0.0-beta.70";
      description = "Pinned Executor v2 self-host container image.";
    };
    allowPrivateFetch = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Allow personal Executor apps to fetch private/tailnet/LAN addresses.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ctl];

    home.activation.executorServer =
      lib.mkIf cfg.server.enable
      (lib.hm.dag.entryAfter ["linkGeneration"] ''
        if [ -z "''${DRY_RUN:-}" ]; then
          # Tailnet-only HTTPS front (no Funnel); persistent in tailscaled, other Serve ports untouched.
          if ! /usr/bin/tailscale serve --bg --https=${toString cfg.httpsPort} --yes "http://127.0.0.1:${toString cfg.port}" >/dev/null; then
            echo "executor: could not publish personal HTTPS endpoint (Tailscale Serve :${toString cfg.httpsPort})" >&2
          fi
        fi
      '');

    systemd.user.services.executor-personal = lib.mkIf cfg.server.enable {
      Unit = {
        Description = "Personal Executor v2 self-host gateway (Docker)";
        Documentation = ["https://executor.sh/docs/run/self-host"];
        After = ["network-online.target"];
        StartLimitIntervalSec = 0;
      };
      Service = {
        Type = "simple";
        ExecStart = "${startServer}";
        ExecStop = "${stopServer}";
        TimeoutStartSec = 300;
        TimeoutStopSec = 45;
        # Upstream docs recommend always/unless-stopped rather than on-failure.
        Restart = "always";
        RestartSec = 10;
      };
      Install.WantedBy = ["default.target"];
    };
  };
}
