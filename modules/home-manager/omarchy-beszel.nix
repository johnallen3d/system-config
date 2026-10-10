# Omarchy-only host metrics. Pairing material is provisioned on the machine,
# never interpolated into a Nix expression or copied into the Nix store.
{pkgs, ...}: {
  systemd.user.services.beszel-agent = {
    Unit = {
      Description = "Beszel host metrics (outbound-only)";
      Documentation = ["https://beszel.dev/guide/agent-installation"];
      After = ["network-online.target"];
      ConditionPathExists = [
        "%h/.config/beszel-agent/hub.pub"
        "%h/.config/beszel-agent/token"
      ];
    };
    Service = {
      ExecStart = "${pkgs.beszel}/bin/beszel-agent";
      Environment = [
        # Existing split DNS resolves this HTTPS endpoint to pi-01's LAN IP.
        "HUB_URL=https://beszel.jallen7usa.com"
        "KEY_FILE=%h/.config/beszel-agent/hub.pub"
        "TOKEN_FILE=%h/.config/beszel-agent/token"
        "DATA_DIR=%S/beszel-agent-data"
        "DISABLE_SSH=true"
        # An explicitly empty value disables container discovery/socket access.
        "DOCKER_HOST="
      ];
      StateDirectory = "beszel-agent-data";
      StateDirectoryMode = "0700";
      UMask = "0077";
      Restart = "always";
      RestartSec = 10;
      NoNewPrivileges = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      RestrictAddressFamilies = ["AF_UNIX" "AF_INET" "AF_INET6"];
      # Leave /proc and /sys visible for unprivileged host metrics. StateDirectory
      # remains writable under ProtectSystem/ProtectHome, preserving pairing.
    };
    Install.WantedBy = ["default.target"];
  };
}
