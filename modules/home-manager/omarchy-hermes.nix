# Omarchy's native Hermes gateway. Runtime policy belongs to upstream Hermes.
{
  config,
  hermes,
  lib,
  pkgs,
  ...
}: let
  cfg = config.nativeHermes;
  homeDir = config.home.homeDirectory;
  runtimePkgs = hermes.inputs.nixpkgs.legacyPackages.${pkgs.stdenv.hostPlatform.system};
  # Upstream's constructor calls this argument python312; this revision needs 3.13.
  runtimeScope = runtimePkgs // {
    python312 = runtimePkgs.python313;
    callPackage = runtimePkgs.lib.callPackageWith runtimeScope;
  };
  runtime = runtimeScope.callPackage "${hermes.outPath}/nix/hermes-agent.nix" {
    inherit (hermes.inputs) uv2nix pyproject-nix pyproject-build-systems;
    npm-lockfile-fix = hermes.inputs.npm-lockfile-fix.packages.${pkgs.stdenv.hostPlatform.system}.default;
    extraDependencyGroups = ["messaging"];
    rev = hermes.rev;
  };
  # Keep the existing production state and isolated home; never re-import NAS data.
  paths = {
    state = "${homeDir}/.local/state/hermes-native/production/baseline-0.21.2";
    home = "${homeDir}/.local/share/hermes-native/production/baseline-0.21.2/home";
    config = "${homeDir}/.config/hermes-native/production/baseline-0.21.2";
    cache = "${homeDir}/.cache/hermes-native/production/baseline-0.21.2";
  };
  vault = "${homeDir}/notes";
  # Match upstream's service name for a non-default HERMES_HOME.
  serviceName = "hermes-gateway-${builtins.substring 0 8 (builtins.hashString "sha256" paths.state)}";
  tools = import ./hermes-native/tools.nix {inherit pkgs runtimePkgs;};
  taskPath = lib.makeBinPath ((builtins.attrValues tools) ++ [
    runtimePkgs.bash
    runtimePkgs.coreutils
    runtimePkgs.gnugrep
    runtimePkgs.gnused
    runtimePkgs.gawk
    runtimePkgs.findutils
    runtimePkgs.time
    runtimePkgs.python313
    runtimePkgs.uv
    runtime.hermesNpmLib.nodejs
    pkgs.usage
  ]);
  environment = {
    HOME = paths.home;
    HERMES_HOME = paths.state;
    HERMES_MANAGED = "home-manager";
    HERMES_GATEWAY_EXTERNAL_SUPERVISOR = "1";
    # Command plugins belong to the trusted notes project, not the Nix store.
    HERMES_ENABLE_PROJECT_PLUGINS = "1";
    XDG_CONFIG_HOME = paths.config;
    XDG_CACHE_HOME = paths.cache;
    XDG_DATA_HOME = "${paths.home}/.local/share";
    XDG_STATE_HOME = "${paths.home}/.local/state";
    PATH = taskPath + ":" + lib.makeBinPath [
      runtimePkgs.git
      runtimePkgs.ripgrep
      runtimePkgs.openssh
      runtimePkgs.ffmpeg
    ];
    UV_CACHE_DIR = "${paths.cache}/uv";
    UV_PYTHON_DOWNLOADS = "never";
    UV_NO_MANAGED_PYTHON = "1";
    UV_OFFLINE = "1";
    PYTHONNOUSERSITE = "1";
    PYTHONDONTWRITEBYTECODE = "1";
    SSL_CERT_FILE = "${runtimePkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
    NIX_SSL_CERT_FILE = "${runtimePkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
    LANG = "C.UTF-8";
    TZ = "America/New_York";
    TZDIR = "${runtimePkgs.tzdata}/share/zoneinfo";
    TERM = "xterm-256color";
    NO_COLOR = "1";
    HERMES_NATIVE_MISE = "${tools.mise}/bin/mise";
    HERMES_NATIVE_TASK_PATH = taskPath;
    HERMES_NATIVE_TASK_PYTHON = "${tools.task-python}/bin/python3";
    HERMES_NATIVE_FONT = "${runtimePkgs.dejavu_fonts}/share/fonts/truetype/DejaVuSans.ttf";
    FONTCONFIG_FILE = runtimePkgs.makeFontsConf {fontDirectories = [runtimePkgs.dejavu_fonts];};
    PLAYWRIGHT_BROWSERS_PATH = runtimePkgs.playwright-driver.browsers;
    NOTEBOOKLM_HOME = "${paths.home}/.notebooklm";
    MISE_AUTO_INSTALL = "0";
    MISE_TRUSTED_CONFIG_PATHS = vault;
    MISE_CONFIG_DIR = "${paths.config}/mise";
    MISE_DATA_DIR = "${paths.home}/.local/share/mise";
    MISE_CACHE_DIR = "${paths.cache}/mise";
    MISE_DISABLE_TOOLS = "uv,sd,yq,npm:defuddle";
    VAULT_DIR = vault;
    VLT_VAULT_PATH = vault;
    VLT_VAULT = "Personal";
    GOG_HOME = "${paths.state}/gogcli";
    HERMES_TIMEZONE = "America/New_York";
    HERMES_EXEC_ASK = "true";
    HERMES_REDACT_SECRETS = "true";
    TELEGRAM_REACTIONS = "true";
    TERMINAL_ENV = "local";
    TERMINAL_CWD = vault;
  };
  launcher = pkgs.writeShellScriptBin "hermes-production" ''
    exec ${pkgs.coreutils}/bin/env -i \
      XDG_RUNTIME_DIR="''${XDG_RUNTIME_DIR:-/run/user/$(${pkgs.coreutils}/bin/id -u)}" \
      ${lib.escapeShellArgs (lib.mapAttrsToList (key: value: "${key}=${value}") environment)} \
      ${runtime}/bin/hermes "$@"
  '';
  nativeLauncher = pkgs.writeShellScriptBin "hermes-native" ''
    exec ${launcher}/bin/hermes-production "$@"
  '';
  stateRelative = ".local/state/hermes-native/production/baseline-0.21.2";
  morningBrief = pkgs.writeShellScript "hermes-morning-brief" ''
    set -euo pipefail
    cd ${lib.escapeShellArg vault}
    export MORNING_BRIEF_DELIVERY=stdout
    exec ${tools.mise}/bin/mise run morning-brief
  '';
in {
  options.nativeHermes.enable = lib.mkEnableOption "the native Hermes gateway on Omarchy";

  config = lib.mkIf cfg.enable {
    home.packages = [launcher nativeLauncher];
    home.file = {
      ".local/bin/hermes-production".source = "${launcher}/bin/hermes-production";
      ".local/bin/hermes-native".source = "${nativeLauncher}/bin/hermes-native";
      # Expose the user unit to Hermes's isolated HOME so its own gateway
      # status/restart commands can find the upstream-named service.
      ".local/share/hermes-native/production/baseline-0.21.2/home/.config/systemd/user/${serviceName}.service".source =
        config.lib.file.mkOutOfStoreSymlink "${homeDir}/.config/systemd/user/${serviceName}.service";
    };
    # Non-secret inspection metadata only; not an approval or execution gate.
    xdg.configFile."hermes-native/production.json".text = builtins.toJSON {
      schemaVersion = 1;
      inherit paths environment vault;
      version = "0.21.2";
      revision = hermes.rev;
      package = toString runtime;
      python = "${runtime.hermesVenv}/bin/python3";
      launcher = "${launcher}/bin/hermes-production";
      service = "${serviceName}.service";
    };
    home.activation.hermesNativeDirectories = lib.hm.dag.entryBetween ["reloadSystemd"] ["linkGeneration"] ''
      run ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArgs ((builtins.attrValues paths) ++ ["${paths.state}/scripts"])}
      # Upstream cron requires a real file within HERMES_HOME/scripts, not a
      # symlink escaping to the Nix store. Install the managed script normally.
      run ${pkgs.coreutils}/bin/install -m 0700 ${morningBrief} ${lib.escapeShellArg "${paths.state}/scripts/morning-brief.sh"}
    '';
    systemd.user.services.${serviceName} = {
      Unit.Description = "Hermes gateway";
      Service = {
        Type = "simple";
        ExecStart = "${launcher}/bin/hermes-production gateway run";
        WorkingDirectory = vault;
        Environment = lib.mapAttrsToList (key: value: "${key}=${value}") environment;
        UMask = "0077";
        Restart = "on-failure";
        RestartSec = 5;
        TimeoutStopSec = 90;
        NoNewPrivileges = true;
        StandardOutput = "journal";
        StandardError = "journal";
      };
      Install.WantedBy = ["default.target"];
    };
  };
}
