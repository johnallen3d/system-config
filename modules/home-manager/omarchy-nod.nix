# Omarchy-only n8n Nod server: upstream's self-host Compose stack, built from a
# pinned release and bound to loopback. pi-01 Caddy serves it at publicUrl
# through a LAN-only forwarder; native UFW must allow pi-01 to lanAddress:4310.
# Secrets come from Doppler nod/prd at start (Compose interpolates them from the
# environment); nothing secret is written to disk or the Nix store.
{
  lib,
  pkgs,
  ...
}: let
  src = pkgs.fetchFromGitHub {
    owner = "n8n-io";
    repo = "nod";
    rev = "nod-v0.8.1";
    hash = "sha256-pNuZ/FjD0GAnfuxyc4ycihnctcPX0iR+2r07Kv+SAcw=";
  };
  selfHost = "${src}/deployment/self-host";
  # Nonsecret settings for the server container's env_file.
  envFile = pkgs.writeText "nod.env" ''
    NOD_ANALYTICS_ENABLED=false
  '';
  port = 4310;
  # Omarchy's reserved physical LAN address, never the Tailscale interface.
  lanAddress = "192.168.4.26";
  publicUrl = "https://marvin.jallen7usa.com";
  # Arch's Docker Engine and Compose plugin (socket-activated system service).
  # A user manager started before the docker group membership lacks the group,
  # so pick it up with util-linux newgrp (setuid, no password for members).
  compose = pkgs.writeShellScript "nod-compose" ''
    set -euo pipefail
    cmd=(/usr/bin/docker compose --project-directory ${selfHost} \
      --file ${selfHost}/compose.yaml "$@")
    if id -nG | grep -qw docker; then exec "''${cmd[@]}"; fi
    SHELL=/bin/sh exec /usr/bin/newgrp docker -c "exec ''${cmd[*]@Q}"
  '';
  doppler = lib.concatStringsSep " " [
    (lib.getExe pkgs.doppler)
    "run --no-read-env --no-check-version --no-fallback --project nod --config prd"
  ];
in {
  systemd.user.services.nod = {
    Unit = {
      Description = "n8n Nod personal agent server (Docker Compose)";
      Documentation = ["https://nod.n8n.io/docs/deploy/self-host/"];
      After = ["network-online.target"];
      # Keep retrying while Doppler is unreachable (no on-disk fallback).
      StartLimitIntervalSec = 0;
    };
    Service = {
      Environment = [
        "COMPOSE_PROJECT_NAME=nod"
        "NOD_ENV_FILE=${envFile}"
        "NOD_PUBLIC_URL=${publicUrl}"
      ];
      # Foreground `up` keeps activation non-blocking while images build.
      ExecStart = "${doppler} -- ${compose} up --build --remove-orphans";
      ExecStop = "${doppler} -- ${compose} stop";
      TimeoutStopSec = 120;
      Restart = "on-failure";
      RestartSec = 30;
    };
    Install.WantedBy = ["default.target"];
  };

  # Plain TCP, so Host, WebSockets and streaming pass through to Caddy untouched.
  systemd.user.services.nod-lan = {
    Unit.Description = "LAN-only TCP proxy for Nod";
    Service = {
      ExecStart = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd 127.0.0.1:${toString port}";
      NoNewPrivileges = true;
    };
  };

  systemd.user.sockets.nod-lan = {
    Unit.Description = "Nod on ${lanAddress}:${toString port} (not the Tailscale interface)";
    Socket = {
      ListenStream = "${lanAddress}:${toString port}";
      FreeBind = true;
      NoDelay = true;
    };
    Install.WantedBy = ["sockets.target"];
  };
}
