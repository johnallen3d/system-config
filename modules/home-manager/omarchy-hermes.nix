# Native, opt-in staging only (#755). NAS remains production until #763.
{
  config,
  hermes,
  lib,
  pkgs,
  ...
}: let
  cfg = config.nativeHermes;
  homeDir = config.home.homeDirectory;
  version = "0.21.2";
  runtimePkgs = hermes.inputs.nixpkgs.legacyPackages.${pkgs.stdenv.hostPlatform.system};
  # The baseline constructor names its Python argument python312 and uses a
  # nested callPackage for the sealed venv. Override both in a private scope,
  # not host nixpkgs, to keep wrapper/site-packages/venv on supported Python 3.13.
  runtimeScope =
    runtimePkgs
    // {
      python312 = runtimePkgs.python313;
      callPackage = runtimePkgs.lib.callPackageWith runtimeScope;
    };
  runtime = runtimeScope.callPackage "${hermes.outPath}/nix/hermes-agent.nix" {
    inherit (hermes.inputs) uv2nix pyproject-nix pyproject-build-systems;
    npm-lockfile-fix = hermes.inputs.npm-lockfile-fix.packages.${pkgs.stdenv.hostPlatform.system}.default;
    extraDependencyGroups = ["messaging"];
    rev = hermes.rev;
  };
  paths = {
    state = "${homeDir}/.local/state/hermes-native/staging/baseline-0.21.2";
    home = "${homeDir}/.local/share/hermes-native/staging/baseline-0.21.2/home";
    config = "${homeDir}/.config/hermes-native/staging/baseline-0.21.2";
    cache = "${homeDir}/.cache/hermes-native/staging/baseline-0.21.2";
  };
  workspace = "${paths.state}/workspace";
  assets = ./hermes-native;
  tools = import ./hermes-native/tools.nix { inherit pkgs runtimePkgs; };
  taskPath = lib.makeBinPath ((builtins.attrValues tools) ++ [
    runtimePkgs.bash runtimePkgs.coreutils runtimePkgs.gnugrep runtimePkgs.gnused
    runtimePkgs.gawk runtimePkgs.findutils runtimePkgs.time runtimePkgs.python313
    runtimePkgs.uv runtime.hermesNpmLib.nodejs pkgs.usage
  ]);
  environment = {
    HOME = paths.home;
    HERMES_HOME = paths.state;
    HERMES_MANAGED = "home-manager";
    XDG_CONFIG_HOME = paths.config;
    XDG_CACHE_HOME = paths.cache;
    XDG_DATA_HOME = "${paths.home}/.local/share";
    XDG_STATE_HOME = "${paths.home}/.local/state";
    # Private child/service PATH only; the unrestricted package is not installed
    # in the workstation profile. Doctor can resolve its Nix-owned command.
    PATH = taskPath + ":" + lib.makeBinPath [
      runtime
      runtimePkgs.python313
      runtimePkgs.uv
      runtime.hermesNpmLib.nodejs
      runtimePkgs.bash
      runtimePkgs.coreutils
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
    # Sealed namespaces have no host /usr/share/zoneinfo. libc/GNU date needs
    # the pinned data explicitly; otherwise TZ silently falls back to UTC.
    TZDIR = "${runtimePkgs.tzdata}/share/zoneinfo";
    TERM = "dumb";
    NO_COLOR = "1";
    HERMES_NATIVE_STAGE = "capabilities-offline";
    HERMES_NATIVE_ASSETS = toString assets;
    HERMES_NATIVE_MISE = "${tools.mise}/bin/mise";
    HERMES_NATIVE_TASK_PATH = taskPath;
    HERMES_NATIVE_TASK_PYTHON = "${tools.task-python}/bin/python3";
    HERMES_NATIVE_FONT = "${runtimePkgs.dejavu_fonts}/share/fonts/truetype/DejaVuSans.ttf";
    FONTCONFIG_FILE = runtimePkgs.makeFontsConf { fontDirectories = [runtimePkgs.dejavu_fonts]; };
    PLAYWRIGHT_BROWSERS_PATH = toString runtimePkgs.playwright-driver.browsers;
    # #760: integration HOME is distinct from HERMES_HOME; use the contract's
    # minimal default profile, not the old empty state/notebooklm seed path.
    NOTEBOOKLM_HOME = "${paths.home}/.notebooklm";
    HERMES_NATIVE_GOG = "${tools.gog}/bin/gog";
    HERMES_NATIVE_NOTEBOOKLM = "${tools.notebooklm}/bin/notebooklm";
    HERMES_NATIVE_CLI = "${runtime}/bin/hermes";
    MISE_AUTO_INSTALL = "0";
    MISE_TRUSTED_CONFIG_PATHS = "${workspace}/notes";
    VAULT_DIR = "${workspace}/notes";
    VLT_VAULT_PATH = "${workspace}/notes";
    VLT_VAULT = "Personal";
    GOG_HOME = "${paths.state}/gogcli";
    GOG_READONLY = "0";
    GOG_ENABLE_COMMANDS_EXACT = "calendar.calendars,calendar.events,calendar.event,calendar.raw,calendar.freebusy,calendar.conflicts,calendar.search,calendar.colors,calendar.time,calendar.create,calendar.update,calendar.delete,calendar.respond,config.get,auth.list";
    HERMES_TIMEZONE = "America/New_York";
    HERMES_EXEC_ASK = "true";
    HERMES_REDACT_SECRETS = "true";
    TELEGRAM_REACTIONS = "true";
    # Never inherit a real-vault cwd or container terminal backend.
    TERMINAL_ENV = "local";
    TERMINAL_CWD = workspace;
  };
  production = import ./hermes-native/production-module.nix {
    inherit config lib pkgs runtime runtimePkgs environment assets version;
    revision = hermes.rev;
  };
  envArgs = lib.escapeShellArgs (lib.mapAttrsToList (key: value: "${key}=${value}") environment);
  # #759: closed public routes, no generic shell/task/writable-vault argument.
  vaultEnvArgs = lib.escapeShellArgs (lib.mapAttrsToList (key: value: "${key}=${value}") (environment // {
    HOME = "/tmp/vault-home";
    HERMES_HOME = "/tmp/vault-state";
    XDG_CONFIG_HOME = "/tmp/vault-config";
    XDG_CACHE_HOME = "/tmp/vault-cache";
    XDG_DATA_HOME = "/tmp/vault-data";
    XDG_STATE_HOME = "/tmp/vault-state";
    VAULT_DIR = "/vault-readonly";
    VLT_VAULT_PATH = "/vault-readonly";
    MISE_TRUSTED_CONFIG_PATHS = "/nonexistent";
    HERMES_NATIVE_SYNCTHING = "${config.services.syncthing.package}/bin/syncthing";
  }));
  launcher = pkgs.writeShellApplication {
    name = "hermes-native";
    text = ''
      # The only new operation is a fixed, Nix-owned offline self-check. No arbitrary
      # command, plugin arguments, interpreter, task, or script can be selected.
      if [ "$#" = 1 ] && [ "$1" = capability-check ]; then
        umask 077
        exec ${pkgs.coreutils}/bin/env -i ${envArgs} HERMES_NATIVE_OFFLINE=1 \
          ${pkgs.bubblewrap}/bin/bwrap --unshare-all --die-with-parent --new-session \
          --ro-bind /nix/store /nix/store --proc /proc --dev /dev --tmpfs /dev/shm --tmpfs /tmp \
          --tmpfs /home --dir /etc --dir /usr --dir /usr/bin --dir /bin \
          --symlink ${runtimePkgs.coreutils}/bin/env /usr/bin/env \
          --symlink ${runtimePkgs.bash}/bin/bash /bin/bash \
          --symlink ${runtimePkgs.bash}/bin/sh /bin/sh --chdir /tmp \
          ${runtime.hermesVenv}/bin/python3 -I ${assets}/check.py ${assets}
      fi
      if [ "$#" = 1 ] && [ "$1" = vault-check ]; then
        umask 077
        # Same-UID production access exists ONLY under a read-only mount, with
        # the rest of host home, proc PIDs, profiles, sockets and network absent.
        [ -d ${lib.escapeShellArg "${homeDir}/notes"} ] && [ ! -L ${lib.escapeShellArg "${homeDir}/notes"} ] || exit 64
        exec ${pkgs.coreutils}/bin/env -i ${vaultEnvArgs} HERMES_VAULT_MODE=read-only \
          ${pkgs.bubblewrap}/bin/bwrap --unshare-all --die-with-parent --new-session \
          --ro-bind /nix/store /nix/store --proc /proc --dev /dev --tmpfs /dev/shm --tmpfs /tmp \
          --tmpfs /home --ro-bind ${lib.escapeShellArg "${homeDir}/notes"} /vault-readonly \
          --dir /tmp/vault-home --dir /etc --dir /usr --dir /usr/bin --dir /bin \
          --symlink ${runtimePkgs.coreutils}/bin/env /usr/bin/env \
          --symlink ${runtimePkgs.bash}/bin/bash /bin/bash --chdir /tmp \
          ${runtime.hermesVenv}/bin/python3 -I ${assets}/vault-safety.py read-check
      fi
      if [ "$#" = 1 ] && [ "$1" = vault-safety-check ]; then
        umask 077
        fixture="$(${pkgs.coreutils}/bin/mktemp -d ${lib.escapeShellArg "${workspace}/vault-fixture-759.XXXXXXXX"})"
        printf '%s\\n' 'SYNTHETIC READ ONLY' > "$fixture/note.md"
        ${pkgs.coreutils}/bin/ln -s note.md "$fixture/alias.md"
        ${pkgs.coreutils}/bin/ln -s ${lib.escapeShellArg "${homeDir}/notes"} "$fixture/external"
        exec ${pkgs.coreutils}/bin/env -i ${vaultEnvArgs} HERMES_VAULT_MODE=disposable \
          ${pkgs.bubblewrap}/bin/bwrap --unshare-all --die-with-parent --new-session \
          --ro-bind /nix/store /nix/store --proc /proc --dev /dev --tmpfs /dev/shm --tmpfs /tmp \
          --tmpfs /home --ro-bind "$fixture" /fixture-ro --dir /etc --dir /usr --dir /usr/bin --dir /bin \
          --symlink ${runtimePkgs.coreutils}/bin/env /usr/bin/env \
          --symlink ${runtimePkgs.bash}/bin/bash /bin/bash --chdir /tmp \
          ${runtime.hermesVenv}/bin/python3 -I ${assets}/vault-fixture.py
      fi
      if [ "$#" = 1 ] && { [ "$1" = state-check ] || [ "$1" = integration-check ]; }; then
        umask 077
        network=()
        operation=state-check
        if [ "$1" = integration-check ]; then
          # Fixed read-only provider/Calendar/passive NotebookLM checks ONLY.
          # No arbitrary interpreter/task/URL, refresh-token rotation, polling,
          # inference, sends, note content or write API is exposed by this route.
          network=(--share-net --ro-bind /etc/resolv.conf /etc/resolv.conf)
          operation=integrations
        fi
        exec ${pkgs.coreutils}/bin/env -i ${envArgs} \
          ${pkgs.bubblewrap}/bin/bwrap --unshare-all --die-with-parent --new-session \
          --ro-bind /nix/store /nix/store --proc /proc --dev /dev --tmpfs /dev/shm --tmpfs /tmp --tmpfs /home \
          --ro-bind ${lib.escapeShellArg paths.state} ${lib.escapeShellArg paths.state} \
          --ro-bind ${lib.escapeShellArg paths.home} ${lib.escapeShellArg paths.home} \
          --ro-bind ${lib.escapeShellArg paths.config} ${lib.escapeShellArg paths.config} \
          --ro-bind ${lib.escapeShellArg paths.cache} ${lib.escapeShellArg paths.cache} \
          --dir /etc --dir /usr --dir /usr/bin --dir /bin \
          --symlink ${runtimePkgs.coreutils}/bin/env /usr/bin/env \
          --symlink ${runtimePkgs.bash}/bin/bash /bin/bash --symlink ${runtimePkgs.bash}/bin/sh /bin/sh \
          "''${network[@]}" --chdir ${lib.escapeShellArg workspace} \
          ${runtime.hermesVenv}/bin/python3 -I ${assets}/state-stage.py "$operation"
      fi
      case "$*" in
        --version) operation=cli-version ;;
        --help) operation=cli-help ;;
        doctor) operation=cli-doctor ;;
        *)
          printf '%s\n' 'Native Hermes is isolated staging: only --version, --help, doctor, capability-check, vault-check, vault-safety-check, state-check and fixed integration-check are enabled. Gateway, inference, schedules and production vault writes remain blocked (#756/#763).' >&2
          exit 64
          ;;
      esac
      umask 077
      cd ${lib.escapeShellArg workspace}
      exec ${pkgs.coreutils}/bin/env -i ${envArgs} \
        ${pkgs.bubblewrap}/bin/bwrap --unshare-all --die-with-parent --new-session \
        --ro-bind /nix/store /nix/store --proc /proc --dev /dev --tmpfs /dev/shm --tmpfs /tmp --tmpfs /home \
        --ro-bind ${lib.escapeShellArg paths.state} ${lib.escapeShellArg paths.state} \
        --ro-bind ${lib.escapeShellArg paths.home} ${lib.escapeShellArg paths.home} \
        --ro-bind ${lib.escapeShellArg paths.config} ${lib.escapeShellArg paths.config} \
        --ro-bind ${lib.escapeShellArg paths.cache} ${lib.escapeShellArg paths.cache} \
        --dir /etc --dir /usr --dir /usr/bin --dir /bin \
        --symlink ${runtimePkgs.coreutils}/bin/env /usr/bin/env \
        --symlink ${runtimePkgs.bash}/bin/bash /bin/bash --chdir ${lib.escapeShellArg workspace} \
        ${runtime.hermesVenv}/bin/python3 -I ${assets}/state-stage.py "$operation"
    '';
  };
  # This is a seed, not a managed symlink: later state migration owns updates.
  seed = pkgs.writeText "hermes-native-staging-seed.json" (builtins.toJSON {
    terminal = {
      backend = "local";
      cwd = workspace;
    };
    platform_toolsets = {
      cli = [];
      telegram = [];
    };
    platforms.telegram.enabled = false;
    mcp_servers = {};
    plugins.enabled = [];
  });
  initializeDirectories = pkgs.writeText "hermes-native-staging-directories.py" ''
    import os
    from pathlib import Path
    from hermes_cli.config import _HERMES_HOME_SUBDIRS

    root = Path(os.environ["HERMES_HOME"])
    for relative in _HERMES_HOME_SUBDIRS:
        path = root / relative
        if path.is_symlink():
            raise SystemExit("hermes-native: refusing symlink state directory " + str(path))
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
  '';
  initializeConfig = pkgs.writeText "hermes-native-staging-config.py" ''
    import json
    import os
    from pathlib import Path
    from hermes_cli.config import DEFAULT_CONFIG

    seed = json.loads(Path("${seed}").read_text())
    seed["_config_version"] = DEFAULT_CONFIG["_config_version"]
    path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
    with path.open("x") as stream:
        json.dump(seed, stream, indent=2)
        stream.write("\n")
  '';
in {
  options.nativeHermes.enable = lib.mkEnableOption "isolated native Hermes foundation on Omarchy";

  config = lib.mkIf cfg.enable {
    home.packages = [launcher production.launcher];
    home.file.".local/bin/hermes-production".source = "${production.launcher}/bin/hermes-production";
    xdg.configFile."hermes-native/production.json".text = builtins.toJSON production.metadata;
    home.activation.hermesNativeProduction = production.activation;
    systemd.user.services.hermes-production = production.service;
    # Preserve Omarchy's user-owned ~/.local/bin/hermes and its mise installer.
    home.file.".local/bin/hermes-native".source = "${launcher}/bin/hermes-native";
    xdg.configFile."hermes-native/runtime.json".text = builtins.toJSON {
      schemaVersion = 1;
      stage = "capabilities-offline";
      assetOwner = "system-config";
      managedAssets = toString assets;
      reconciler = "${assets}/reconcile.py";
      offlineCheck = "${assets}/check.py";
      toolVersions = lib.mapAttrs (_: package: package.version) tools;
      tools = lib.mapAttrs (_: package: toString package) tools;
      vaultSafety = {
        productionWrites = "DISABLED";
        productionPath = "${homeDir}/notes";
        readOnlyView = "/vault-readonly";
        readCheck = "vault-check";
        disposableCheck = "vault-safety-check";
        operator = "${assets}/vault-safety.py";
        snapshots = "${homeDir}/.local/state/hermes-native/vault-snapshots";
        syncthing = "${config.services.syncthing.package}/bin/syncthing";
        approval = "No production enable/restore route; exact mutation and all-peer exclusion/restore authority required at #762/#763";
      };
      stateStaging = {
        operator = "${assets}/state-stage.py";
        archives = "${homeDir}/.local/state/hermes-native/state-imports/baseline-0.21.2";
        kind = "NON_AUTHORITATIVE_STAGING";
        consistency = "PER_DATABASE_ONLINE_BACKUP_NOT_GLOBAL";
        readCheck = "state-check";
        integrationCheck = "integration-check";
        gogPasswordSource = "Doppler notes/prd GOG_KEYRING_PASSWORD -> private stdin -> GOG_HOME/keyring-password";
        telegramProvisioning = "NOT_STAGED; #763-only canonical NANOBOT_TELEGRAM_TOKEN; no executable staging secret";
        codexRefresh = "FORBIDDEN_WHILE_NAS_OWNS_ROTATING_GRANT; expiry requires fresh export, never auto-refresh";
      };
      morningBrief = "INACTIVE";
      privateSkillAdoption = "six-skills/nine-files fully reviewed; privately staged outside discovery; per-skill enabling gates pending";
      privateSkillsStaging = "${homeDir}/.local/state/hermes-native/private-skills-staged/baseline-0.21.2";
      foodPolicyDrift = "resolved-preserve-live-disclosed-estimates";
      notebooklm = "notebooklm-py[browser]==0.8.2; Nix-owned offline closure; auth/integration remains #760";
      inherit version paths workspace environment;
      revision = hermes.rev;
      package = toString runtime;
      python = "${runtime.hermesVenv}/bin/python3";
      uv = "${runtimePkgs.uv}/bin/uv";
      node = "${runtime.hermesNpmLib.nodejs}/bin/node";
      npm = "${runtime.hermesNpmLib.nodejs}/bin/npm";
      pythonVersion = runtimePkgs.python313.version;
      source = toString hermes.outPath;
      launcher = "${launcher}/bin/hermes-native";
      gatewayEnabled = false;
      productionStateTransferred = false;
    };

    home.activation.hermesNativeStaging = lib.hm.dag.entryAfter ["writeBoundary"] ''
      (
        set -eu
        umask 077
        for directory in ${lib.escapeShellArgs (["${homeDir}/.local/state/hermes-native" "${homeDir}/.local/share/hermes-native" "${homeDir}/.config/hermes-native" "${homeDir}/.cache/hermes-native"] ++ (builtins.attrValues paths) ++ [workspace "${paths.state}/logs" "${homeDir}/.local/state/hermes-native/state-imports/baseline-0.21.2"])}; do
          if [ -L "$directory" ]; then
            printf 'hermes-native: refusing symlink state directory %s\n' "$directory" >&2
            exit 1
          fi
          run ${pkgs.coreutils}/bin/install -d -m 0700 "$directory"
        done
        # Managed mode will not create its missing skeleton at runtime. Obtain
        # the exact required directories from the pinned installed Python code.
        run ${pkgs.coreutils}/bin/env -i ${envArgs} ${runtime.hermesVenv}/bin/python3 -I ${initializeDirectories}
        for file in ${lib.escapeShellArgs ["${paths.state}/config.yaml" "${paths.state}/.env"]}; do
          if [ -L "$file" ]; then
            printf 'hermes-native: refusing symlink config/credential file %s\n' "$file" >&2
            exit 1
          fi
        done
        if [ ! -e ${lib.escapeShellArg "${paths.state}/config.yaml"} ]; then
          run ${pkgs.coreutils}/bin/env -i ${envArgs} ${runtime.hermesVenv}/bin/python3 -I ${initializeConfig}
        fi
        if [ ! -e ${lib.escapeShellArg "${paths.state}/.env"} ]; then
          run ${pkgs.coreutils}/bin/install -m 0600 /dev/null ${lib.escapeShellArg "${paths.state}/.env"}
        fi
        run ${pkgs.coreutils}/bin/env -i ${envArgs} ${runtime.hermesVenv}/bin/python3 -I ${assets}/reconcile.py \
          --state ${lib.escapeShellArg paths.state} --assets ${assets}
      )
    '';

    # Deliberately static/unstartable, even via `systemctl --user start`.
    # No WantedBy, timer, credential file or startup/linger policy changes.
    systemd.user.services.hermes-native = {
      Unit = {
        Description = "Native Hermes gateway (blocked staging; NAS remains production)";
        RefuseManualStart = true;
      };
      Service = {
        Type = "simple";
        ExecStart = "${launcher}/bin/hermes-native gateway run";
        WorkingDirectory = workspace;
        Environment = lib.mapAttrsToList (key: value: "${key}=${value}") environment;
        UMask = "0077";
        StandardOutput = "journal";
        StandardError = "journal";
        Restart = "no";
        NoNewPrivileges = true;
      };
    };
  };
}
