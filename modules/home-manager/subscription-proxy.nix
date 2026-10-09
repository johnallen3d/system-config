{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.subscriptionProxy;
  homeDir = config.home.homeDirectory;
  python = pkgs.python3.withPackages (ps: [ps.pyyaml]);
  manager = pkgs.writeShellApplication {
    name = "subscription-proxy";
    runtimeInputs = [pkgs.curl] ++ lib.optionals pkgs.stdenv.hostPlatform.isLinux [pkgs.wl-clipboard];
    text = ''exec ${python}/bin/python3 ${./subscription-proxy}/manager.py "$@"'';
  };
  panelHtml = pkgs.fetchurl {
    url = "https://github.com/router-for-me/Cli-Proxy-API-Management-Center/releases/download/v1.26.0/management.html";
    hash = "sha256-quBlPmXcgWaN7XWcjpPUdM4pXgsVmhyiBb8LYxZlXfE=";
  };
  # An immutable, versioned official frontend; upstream auto-updates stay off.
  panel = pkgs.runCommand "subscription-proxy-management-center-1.26.0" {} ''
    mkdir -p "$out"
    ln -s ${panelHtml} "$out/management.html"
  '';
  proxy = import ./packages/cliproxyapi.nix {inherit pkgs;};
  template = pkgs.writeText "subscription-proxy-server.json" (builtins.toJSON {
    host = cfg.address;
    ports = {
      personal = 8317;
      work = 8318;
    };
  });
  endpoints = {
    personal = "http://${cfg.address}:8317";
    work = "http://${cfg.address}:8318";
  };
  refreshArgs = ["${lib.getExe manager}" "refresh-go" "--command" "${lib.getExe manager}"] ++ lib.optional cfg.server.enable "--server";
  refreshEnv = {
    HOME = homeDir;
    PI_CODING_AGENT_DIR = "${homeDir}/.config/pi-work";
    CLAUDE_CONFIG_DIR = "${homeDir}/.config/claude-gmatter";
  };
  service = profile: {
    Unit = {
      Description = "Isolated ${profile} subscription gateway";
      After = ["network-online.target"];
      ConditionPathExists = "${homeDir}/.config/subscription-proxy/server-${profile}.yaml";
    };
    Service = {
      Type = "simple";
      ExecStart = "${lib.getExe proxy} --config ${homeDir}/.config/subscription-proxy/server-${profile}.yaml --local-model";
      WorkingDirectory = "${homeDir}/.local/share/subscription-proxy/${profile}";
      Environment = ["MANAGEMENT_STATIC_PATH=${panel}"];
      Restart = "on-failure";
      RestartSec = 5;
      UMask = "0077";
      NoNewPrivileges = true;
      PrivateTmp = true;
      ProtectSystem = "strict";
      ProtectHome = "read-only";
      ReadWritePaths = [
        "${homeDir}/.config/subscription-proxy"
        "${homeDir}/.local/share/subscription-proxy/${profile}"
      ];
    };
    Install.WantedBy = ["default.target"];
  };
in {
  options.subscriptionProxy = {
    enable = lib.mkEnableOption "central subscription gateway clients and official UI launcher";
    server.enable = lib.mkEnableOption "the isolated Omarchy subscription gateway services";
    address = lib.mkOption {
      type = lib.types.str;
      default = "100.97.112.40";
      description = "Omarchy's stable Tailscale IPv4 address; never a public/LAN listener.";
    };
  };
  config = lib.mkIf cfg.enable {
    home.packages = [manager] ++ lib.optional cfg.server.enable proxy;
    home.file.".local/bin/subscription-proxy".source = "${manager}/bin/subscription-proxy";
    xdg.configFile."subscription-proxy/endpoints.json".text = builtins.toJSON endpoints + "\n";
    home.activation.subscriptionProxyClients =
      lib.hm.dag.entryAfter [
        "linkGeneration"
        "piSettings"
        "piWorkSettings"
        "claudeProfileDefaults"
      ] ''
        if [ -z "''${DRY_RUN:-}" ]; then
          ${lib.getExe manager} configure-client --command ${lib.getExe manager}
        fi
      '';
    home.activation.subscriptionProxyServer =
      lib.mkIf cfg.server.enable
      (lib.hm.dag.entryAfter ["linkGeneration"] ''
        if [ -z "''${DRY_RUN:-}" ]; then
          ${lib.getExe manager} seed-server --template ${template}
        fi
      '');
    home.activation.subscriptionProxyCatalogState = lib.hm.dag.entryAfter ["writeBoundary"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        ${pkgs.coreutils}/bin/install -d -m 0700 "${homeDir}/.local/state/subscription-proxy"
      fi
    '';
    systemd.user.services = lib.mkMerge [
      (lib.mkIf cfg.server.enable {
        subscription-proxy-personal = service "personal";
        subscription-proxy-work = service "work";
      })
      (lib.mkIf pkgs.stdenv.hostPlatform.isLinux {
        subscription-proxy-catalog = {
          Unit = {
            Description = "Reconcile validated non-Claude OpenCode Go models";
            After = ["network-online.target"] ++ lib.optional cfg.server.enable "subscription-proxy-work.service";
            Wants = lib.optional cfg.server.enable "subscription-proxy-work.service";
          };
          Service = {
            Type = "oneshot";
            ExecStart = lib.escapeShellArgs refreshArgs;
            Environment = lib.mapAttrsToList (name: value: "${name}=${value}") refreshEnv;
            UMask = "0077";
            TimeoutStartSec = 180;
            NoNewPrivileges = true;
          };
        };
      })
    ];
    systemd.user.timers.subscription-proxy-catalog = lib.mkIf pkgs.stdenv.hostPlatform.isLinux {
      Unit.Description = "Daily Go catalog refresh (catch up after downtime)";
      Timer = {
        OnCalendar = "*-*-* 03:15:00";
        OnBootSec = "5min";
        RandomizedDelaySec = "10min";
        Persistent = true;
      };
      Install.WantedBy = ["timers.target"];
    };
    launchd.agents.subscription-proxy-catalog = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
      enable = true;
      config = {
        Label = "org.nix-community.home.subscription-proxy-catalog";
        ProgramArguments = refreshArgs;
        EnvironmentVariables = refreshEnv;
        RunAtLoad = true;
        StartInterval = 86400;
        ProcessType = "Background";
        Umask = 63;
        StandardOutPath = "${homeDir}/.local/state/subscription-proxy/catalog.log";
        StandardErrorPath = "${homeDir}/.local/state/subscription-proxy/catalog.err.log";
      };
    };
  };
}
