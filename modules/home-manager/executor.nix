# Central Executor v2 self-host gateways (Omarchy singletons) and tailnet MCP
# client config, mirroring subscription-proxy.nix: one personal and one work
# instance, each with its own container, data volume, and Tailscale Serve port.
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.executor;
  backupDir = "${config.home.homeDirectory}/.local/share/executor/backups";

  instances = {
    personal = {inherit (cfg) origin port httpsPort allowPrivateFetch;};
    work = {inherit (cfg.work) origin port httpsPort allowPrivateFetch;};
  };

  # Arch's Docker Engine is a socket-activated system service; a user manager
  # started before docker group membership needs newgrp (same pattern as other Compose services).
  docker = pkgs.writeShellScript "executor-docker" ''
    set -euo pipefail
    cmd=(/usr/bin/docker "$@")
    if id -nG | grep -qw docker; then exec "''${cmd[@]}"; fi
    SHELL=/bin/sh exec /usr/bin/newgrp docker -c "exec ''${cmd[*]@Q}"
  '';

  startServer = name: inst:
    pkgs.writeShellScript "executor-${name}-start" ''
      set -euo pipefail
      ${docker} rm -f executor-${name} >/dev/null 2>&1 || true
      if ! ${docker} image inspect ${lib.escapeShellArg cfg.image} >/dev/null 2>&1; then
        ${docker} pull ${lib.escapeShellArg cfg.image}
      fi
      exec ${docker} run --rm \
        --name executor-${name} \
        --init \
        -p 127.0.0.1:${toString inst.port}:4400 \
        -v executor-${name}-data:/app/data \
        -e BETTER_AUTH_URL=${lib.escapeShellArg inst.origin} \
        -e EXECUTOR_ENVIRONMENT=${name} \
        -e EXECUTOR_APPS_ALLOW_PRIVATE_FETCH=${lib.boolToString inst.allowPrivateFetch} \
        -e EXECUTOR_APP_WORKERS=32 \
        -e EXECUTOR_MCP_CLIENTS=64 \
        -e EXECUTOR_MCP_CLIENTS_PER_USER=64 \
        -e EXECUTOR_NO_UPDATE_CHECK=1 \
        -e EXECUTOR_DISABLE_ANALYTICS=1 \
        ${lib.escapeShellArg cfg.image}
    '';

  stopServer = name:
    pkgs.writeShellScript "executor-${name}-stop" ''
      set -euo pipefail
      ${docker} stop -t 30 executor-${name} >/dev/null 2>&1 || true
    '';

  ctl = pkgs.writeShellApplication {
    name = "executor-ctl";
    runtimeInputs = [pkgs.curl pkgs.coreutils];
    text = ''
      set -euo pipefail
      instance=personal
      case "''${1:-}" in
        personal|work) instance="$1"; shift ;;
      esac
      case "$instance" in
        personal) origin=${lib.escapeShellArg cfg.origin} ;;
        work) origin=${lib.escapeShellArg cfg.work.origin} ;;
      esac
      cmd="''${1:-ui}"
      case "$cmd" in
        ui)
          echo "Executor $instance dashboard: $origin"
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
        service="executor-$instance.service"
        container="executor-$instance"
        echo "Service:  $(${pkgs.systemd}/bin/systemctl --user is-active "$service" || true)"
        ${docker} ps -a --filter "name=^/$container$" --format 'Container: {{.Names}} ({{.Status}}, {{.Image}})' || true
      ''}
          [ "$code" = 200 ]
          ;;
        ${lib.optionalString cfg.server.enable ''
        backup)
          service="executor-$instance.service"
          volume="executor-$instance-data"
          dest="''${2:-${backupDir}}"
          mkdir -p "$dest"
          chmod 0700 "$dest"
          stamp="$(date +%Y%m%d-%H%M%S)"
          archive="$volume-$stamp.tar.gz"
          was_active=0
          if ${pkgs.systemd}/bin/systemctl --user is-active --quiet "$service"; then
            was_active=1
            ${pkgs.systemd}/bin/systemctl --user stop "$service"
          fi
          trap 'if [ "$was_active" = 1 ]; then ${pkgs.systemd}/bin/systemctl --user start "$service"; fi' EXIT
          ${docker} run --rm \
            -v "$volume:/data:ro" \
            -v "$dest:/backup" \
            alpine:3.21 tar czf "/backup/$archive" -C /data .
          chmod 0600 "$dest/$archive"
          echo "Backed up $volume to $dest/$archive"
          ;;
      ''}
        *)
          echo "Usage: executor-ctl [personal|work] [ui|status${lib.optionalString cfg.server.enable "|backup [dir]"}]" >&2
          exit 2
          ;;
      esac
    '';
  };

  instanceOptions = {
    name,
    scope,
    port,
    httpsPort,
  }: {
    origin = lib.mkOption {
      type = lib.types.str;
      default = "https://omarchy.taila14c2.ts.net:${toString httpsPort}";
      description = "Tailnet-only HTTPS origin of the ${name} instance served by Tailscale Serve (must match BETTER_AUTH_URL).";
    };
    mcpUrl = lib.mkOption {
      type = lib.types.str;
      default = "${scope.origin}/mcp";
      defaultText = lib.literalExpression "\"\${origin}/mcp\"";
      description = "Streamable HTTP MCP endpoint for ${name} Executor clients.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = port;
      description = "Loopback port bound on Omarchy for the ${name} Executor container.";
    };
    httpsPort = lib.mkOption {
      type = lib.types.port;
      default = httpsPort;
      description = "Tailscale Serve HTTPS port exposing the ${name} Executor container on the tailnet.";
    };
    allowPrivateFetch = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Allow ${name} Executor apps to fetch private/tailnet/LAN addresses.";
    };
  };
in {
  options.executor =
    {
      enable = lib.mkEnableOption "central personal and work Executor v2 MCP client wiring and dashboard helper";
      server.enable = lib.mkEnableOption "the Omarchy personal and work Executor v2 self-host Docker services";
      image = lib.mkOption {
        type = lib.types.str;
        default = "ghcr.io/usefulsoftwareco/executor-selfhost:2.0.0-beta.70";
        description = "Pinned Executor v2 self-host container image (shared by both instances).";
      };
      work = instanceOptions {
        name = "work";
        scope = cfg.work;
        port = 4402;
        httpsPort = 4444;
      };
    }
    // instanceOptions {
      name = "personal";
      scope = cfg;
      port = 4401;
      httpsPort = 4443;
    };

  config = lib.mkIf cfg.enable {
    home.packages = [ctl];

    home.activation.executorServer =
      lib.mkIf cfg.server.enable
      (lib.hm.dag.entryAfter ["linkGeneration"] ''
        if [ -z "''${DRY_RUN:-}" ]; then
          # Tailnet-only HTTPS fronts (no Funnel); persistent in tailscaled, other Serve ports untouched.
          ${lib.concatStrings (lib.mapAttrsToList (name: inst: ''
            if ! /usr/bin/tailscale serve --bg --https=${toString inst.httpsPort} --yes "http://127.0.0.1:${toString inst.port}" >/dev/null; then
              echo "executor: could not publish ${name} HTTPS endpoint (Tailscale Serve :${toString inst.httpsPort})" >&2
            fi
          '')
          instances)}
        fi
      '');

    systemd.user.services = lib.mkIf cfg.server.enable (lib.mapAttrs' (name: inst:
      lib.nameValuePair "executor-${name}" {
        Unit = {
          Description = "${name} Executor v2 self-host gateway (Docker)";
          Documentation = ["https://executor.sh/docs/run/self-host"];
          After = ["network-online.target"];
          StartLimitIntervalSec = 0;
        };
        Service = {
          Type = "simple";
          ExecStart = "${startServer name inst}";
          ExecStop = "${stopServer name}";
          TimeoutStartSec = 300;
          TimeoutStopSec = 45;
          # Upstream docs recommend always/unless-stopped rather than on-failure.
          Restart = "always";
          RestartSec = 10;
        };
        Install.WantedBy = ["default.target"];
      })
    instances);
  };
}
