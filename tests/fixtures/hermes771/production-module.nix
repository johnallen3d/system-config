# #763 distinct production foundation. This does not reinterpret staging or
# install a network service. All runtime/poller/scheduler/write entrypoints stay
# refused until the complete cutover controller is validated and armed.
{ config, lib, pkgs, runtime, runtimePkgs, environment, assets, hermesSource, version, revision }:
let
  homeDir = config.home.homeDirectory;
  paths = {
    state = "${homeDir}/.local/state/hermes-native/production/baseline-0.21.2";
    home = "${homeDir}/.local/share/hermes-native/production/baseline-0.21.2/home";
    config = "${homeDir}/.config/hermes-native/production/baseline-0.21.2";
    cache = "${homeDir}/.cache/hermes-native/production/baseline-0.21.2";
  };
  workspace = "${paths.state}/workspace";
  productionEnvironment = environment // {
    HOME = paths.home;
    HERMES_HOME = paths.state;
    HERMES_NATIVE_STAGE = "production";
    HERMES_NATIVE_READONLY = "1";
    HERMES_GATEWAY_EXTERNAL_SUPERVISOR = "1";
    XDG_CONFIG_HOME = paths.config;
    XDG_CACHE_HOME = paths.cache;
    XDG_DATA_HOME = "${paths.home}/.local/share";
    XDG_STATE_HOME = "${paths.home}/.local/state";
    UV_CACHE_DIR = "${paths.cache}/uv";
    NOTEBOOKLM_HOME = "${paths.home}/.notebooklm";
    VAULT_DIR = "${workspace}/notes";
    VLT_VAULT_PATH = "${workspace}/notes";
    MISE_TRUSTED_CONFIG_PATHS = "${workspace}/notes";
    TERMINAL_CWD = workspace;
    GOG_HOME = "${paths.state}/gogcli";
    GOG_READONLY = "1";
    GOG_ENABLE_COMMANDS_EXACT = "calendar.calendars,calendar.events,calendar.event,calendar.raw,calendar.freebusy,calendar.conflicts,calendar.search,calendar.colors,calendar.time,config.get,auth.list";
    HERMES_PRODUCTION_PYTHON = "${runtime.hermesVenv}/bin/python3";
    HERMES_PRODUCTION_OPERATOR = "${assets}/production-runtime.py";
  };
  envArgs = lib.escapeShellArgs (lib.mapAttrsToList (key: value: "${key}=${value}") productionEnvironment);
  launcher = pkgs.writeShellApplication {
    name = "hermes-production";
    text = ''
      [ "$#" = 1 ] || exit 64
      umask 077
      case "$1" in
        check|engineering-components|engineering-providers|engineering-ready|engineering-evidence|import|arm|public-probe|start|gateway|stop|maintenance-task|acceptance-status|acceptance-canary|acceptance-brief|brief-noeffect|continue-brief|final-gate-ready|continue-live|initial-live|brief-request|incident-export|incident-status)
          exec ${pkgs.coreutils}/bin/env -i ${envArgs} \
            ${runtime.hermesVenv}/bin/python3 -I -B ${assets}/production-runtime.py "$1"
          ;;
        *) printf '%s\n' 'Production polling/scheduling/writes/restore remain closed; no staging promotion or implicit unlock.' >&2; exit 64 ;;
      esac
    '';
  };
  metadata = {
    schemaVersion = 1;
    namespace = "production/baseline-0.21.2";
    assetOwner = "system-config";
    managedAssets = toString assets;
    inherit version revision paths workspace;
    environment = productionEnvironment;
    package = toString runtime;
    python = "${runtime.hermesVenv}/bin/python3";
    launcher = "${launcher}/bin/hermes-production";
    operator = "${assets}/production-runtime.py";
    transferOperator = "${assets}/production-transfer.py";
    bubblewrap = "${pkgs.bubblewrap}/bin/bwrap";
    envBinary = "${runtimePkgs.coreutils}/bin/env";
    bashBinary = "${runtimePkgs.bashInteractive}/bin/bash";
    syncthing = "${config.services.syncthing.package}/bin/syncthing";
    service = "hermes-production.service";
    gatewayEnabled = false;
    # Code present is not production ownership/readiness. The real CLOSED
    # receipt, installed fixture evidence and fresh stopped-source arming are
    # mandatory independent gates before the controller can start this unit.
    runtimeEngineeringReady = true;
    # Retain sibling state fixture and relative imports of the installed assets.
    productionFixture = "${hermesSource}/tests/hermes-native-production-transfer.py";
    writerFixture = "${hermesSource}/tests/hermes-native-production-writers.py";
    morningBrief = "CLOSED";
    productionWrites = "CLOSED";
    providerRefresh = "CLOSED_UNTIL_EXCLUSIVE_TRANSFER";
    vault = "${homeDir}/notes";
    coordinator = paths.state;
    peerEvidence = "EXISTING_SYNCTHING_METADATA_NOT_REMOTE_CONTENT_HASHES_OR_DISTRIBUTED_LOCK";
    privateSkillAdoption = "PRIVATE_USER_OWNED_OUTSIDE_DISCOVERY_INDIVIDUAL_GATES";
    retentionDaysMinimum = 14;
  };
in {
  inherit launcher metadata;
  activation = lib.hm.dag.entryAfter ["writeBoundary"] ''
    (
      set -eu
      umask 077
      for directory in ${lib.escapeShellArgs (builtins.attrValues paths)}; do
        [ ! -L "$directory" ] || exit 64
        run ${pkgs.coreutils}/bin/install -d -m 0700 "$directory"
      done
      run ${pkgs.coreutils}/bin/env -i ${envArgs} \
        ${runtime.hermesVenv}/bin/python3 -I -B ${assets}/production-runtime.py initialize
    )
  '';
  service = {
    Unit = {
      Description = "Hermes distinct production namespace (closed #763 engineering gate)";
      RefuseManualStart = true;
    };
    Service = {
      Type = "simple";
      ExecStart = "${launcher}/bin/hermes-production gateway";
      WorkingDirectory = workspace;
      Environment = lib.mapAttrsToList (key: value: "${key}=${value}") productionEnvironment;
      UMask = "0077";
      StandardOutput = "journal";
      StandardError = "journal";
      Restart = "no";
      NoNewPrivileges = true;
    };
  };
}
