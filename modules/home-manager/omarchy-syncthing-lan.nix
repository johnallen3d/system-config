# Omarchy-only LAN access; Syncthing and Tailscale Serve retain their listeners.
{pkgs, ...}: {
  systemd.user.services.syncthing-lan = {
    Unit = {
      Description = "Syncthing GUI LAN forwarder (pi-01 only)";
      After = ["network-online.target" "syncthing.service"];
      Wants = ["syncthing.service"];
    };
    Service = {
      # Fail closed at startup if the existing GUI authentication is missing.
      ExecStartPre = ["${pkgs.python3}/bin/python3 -I ${./omarchy-syncthing/check-auth.py}"];
      # Bind only this LAN address, never wildcard/Tailscale; additionally reject
      # every source except pi-01. Native UFW must allow the same narrow tuple.
      ExecStart = "${pkgs.socat}/bin/socat TCP4-LISTEN:8384,bind=192.168.4.26,reuseaddr,fork,range=192.168.5.11/32 TCP4:127.0.0.1:8384";
      Restart = "always";
      RestartSec = 10;
      UMask = "0077";
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      RestrictAddressFamilies = ["AF_INET" "AF_UNIX"];
    };
    Install.WantedBy = ["default.target"];
  };
}
