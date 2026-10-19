# Omarchy-only Pi Durable trial: real notes read/write; no other agent profile mounts.
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.piPocketTrial;
  homeDir = config.home.homeDirectory;
  package = import ./packages/pi-pocket.nix {inherit pkgs;};
  state = "${homeDir}/.local/state/pi-pocket-trial";
  privateHome = "${state}/home";
  sandboxHome = "/home/pi-pocket";
  profile = "${sandboxHome}/.config/pi-pocket-trial";
  data = "${sandboxHome}/.pi-pocket";
  notesSource = "${homeDir}/notes";
  workspace = "${sandboxHome}/notes";
  port = 8796;
  # Reuse the pinned vlt binary, not Hermes's gateway, credentials or state.
  vaultTools = import ./hermes-native/tools.nix {inherit pkgs; runtimePkgs = pkgs;};
  taskPython = pkgs.python313.withPackages (ps: [ps.pyyaml]);
  helperPi = pkgs.writeShellScriptBin "pi" ''
    exec ${pkgs.nodejs_24}/bin/node ${app}/node_modules/@earendil-works/pi-coding-agent/dist/cli.js "$@"
  '';
  helperUv = pkgs.writeShellScriptBin "uv" ''
    # Food matching is a local PEP723 script. Its dependencies are prebuilt, so
    # neither the helper nor the sandbox needs a package download at runtime.
    if [ "$#" -ge 4 ] && [ "$1" = run ] && [ "$2" = --quiet ] && [ "$3" = --script ]; then
      shift 3
    elif [ "$#" -ge 3 ] && [ "$1" = run ] && [ "$2" = --script ]; then
      shift 2
    else
      exec ${pkgs.uv}/bin/uv "$@"
    fi
    script="$1"; shift
    canonical="$(${pkgs.coreutils}/bin/realpath -e -- "$script")"
    if [ "$canonical" = "''${VAULT_DIR:-/nonexistent}/scripts/food-pick" ]; then
      exec ${taskPython}/bin/python3 -I "$canonical" "$@"
    fi
    exec ${pkgs.uv}/bin/uv run --script "$script" "$@"
  '';
  taskPath = lib.makeBinPath [
    helperPi
    helperUv
    taskPython
    vaultTools.vlt
    pkgs.nodejs_24
    pkgs.bash
    pkgs.coreutils
    pkgs.gitMinimal
    pkgs.ripgrep
    pkgs.fd
    pkgs.mise
    pkgs.usage
    pkgs.yq-go
    pkgs.util-linux
  ];
  app = "${package}/share/pi-pocket";
  # An empty root with explicit mounts, not a writable host home with deny-list
  # exceptions. The host user bus, SSH/GPG sockets, credentials, /etc secrets,
  # Hermes data and host processes are not visible. John authorized read/write
  # access to the whole notes project, not to the rest of the host filesystem.
  sandbox = pkgs.writeShellScriptBin "pi-pocket-trial-sandbox" ''
    set -euo pipefail
    exec ${pkgs.coreutils}/bin/env -i \
      HOME=${sandboxHome} \
      USER=pi-pocket LOGNAME=pi-pocket \
      PATH=${lib.escapeShellArg taskPath} \
      SHELL=${pkgs.bash}/bin/bash \
      PI_CODING_AGENT_DIR=${profile} \
      CLAUDE_CONFIG_DIR=${sandboxHome}/.config/claude-personal \
      XDG_CONFIG_HOME=${sandboxHome}/.config \
      XDG_CACHE_HOME=${sandboxHome}/.cache \
      XDG_DATA_HOME=${sandboxHome}/.local/share \
      XDG_STATE_HOME=${sandboxHome}/.local/state \
      PI_POCKET_DIR=${data} PI_POCKET_SUPERVISED=1 \
      VAULT_DIR=${workspace} VAULT_NAME=${workspace} VLT_VAULT=${workspace} \
      FOOD_LOG_PROVIDER=subscription-codex FOOD_LOG_MODEL=gpt-6-luna \
      MISE_AUTO_INSTALL=0 MISE_TRUSTED_CONFIG_PATHS=${workspace} \
      MISE_DISABLE_TOOLS=uv,sd,yq,npm:defuddle \
      UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never PI_TELEMETRY=0 \
      SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt \
      NODE_EXTRA_CA_CERTS=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt \
      LANG=C.UTF-8 TZ=America/New_York TZDIR=${pkgs.tzdata}/share/zoneinfo \
      TMPDIR=/tmp \
      ${pkgs.bubblewrap}/bin/bwrap \
        --unshare-all --share-net --die-with-parent --new-session --cap-drop ALL \
        --ro-bind /nix/store /nix/store \
        --proc /proc --dev /dev --tmpfs /tmp \
        --dir /etc \
        --ro-bind /etc/resolv.conf /etc/resolv.conf \
        --ro-bind /etc/hosts /etc/hosts \
        --dir /bin --symlink ${pkgs.bash}/bin/bash /bin/bash \
        --symlink ${pkgs.bash}/bin/bash /bin/sh \
        --dir /usr/bin --symlink ${pkgs.coreutils}/bin/env /usr/bin/env \
        --bind ${lib.escapeShellArg privateHome} ${sandboxHome} \
        --bind ${lib.escapeShellArg notesSource} ${workspace} \
        --chdir ${workspace} \
        -- "$@"
  '';
  initialize = pkgs.writeText "pi-pocket-trial-initialize.mjs" ''
    import { ConfigStore } from '${app}/src/server/config.ts';
    import { existsSync, mkdirSync, symlinkSync, readlinkSync } from 'node:fs';
    const directory = process.env.PI_POCKET_DIR;
    // The adapter belongs to notes; link it, rather than copying its logic into Nix.
    const extensions = directory + '/extensions';
    mkdirSync(extensions, { recursive: true });
    for (const name of ['notes-search.ts', 'notes-food.ts']) {
      const adapter = extensions + '/' + name;
      const source = '${workspace}/.pocket/extensions/' + name;
      try {
        symlinkSync(source, adapter);
      } catch (error) {
        if (error.code !== 'EEXIST' || readlinkSync(adapter) !== source) throw error;
      }
    }
    if (!existsSync(directory + '/config.json')) {
      const config = new ConfigStore(directory);
      for (const file of [
        'agent-teams.ts', 'browser.ts', 'gallery.ts', 'goals.ts', 'guard.ts',
        'memory.ts', 'pip.ts', 'schedules.ts', 'subagents.ts', 'triggers.ts',
      ]) config.setExtensionEnabled(file, false);
    }
  '';
  launcher = pkgs.writeShellScript "pi-pocket-trial-server" ''
    set -euo pipefail
    # Namespace-local PIDs cannot arbitrate other namespaces. Keep an additional
    # host-side lifetime lock before any app initialization or live SQLite open.
    exec 9>${lib.escapeShellArg "${state}/server.lock"}
    ${pkgs.util-linux}/bin/flock --nonblock 9
    # Native Tailscale is already managed by Omarchy; never change its Serve map.
    host=$(/usr/bin/tailscale ip -4)
    [[ "$host" =~ ^100\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 78
    ${sandbox}/bin/pi-pocket-trial-sandbox ${pkgs.nodejs_24}/bin/node ${initialize}
    # Upstream prints the owner URL on startup. Keep the bearer token out of the
    # routine journal; retrieve it only deliberately with the login helper.
    ${sandbox}/bin/pi-pocket-trial-sandbox \
      ${pkgs.nodejs_24}/bin/node ${app}/src/server/main.ts \
      --host "$host" --port ${toString port} --data ${data} --cwd ${workspace} \
      2>&1 | ${pkgs.gnused}/bin/sed -u -E \
        's@(https?://[^[:space:]]*/login[?]token=)[^[:space:]]+@\1[redacted]@g'
  '';
  login = pkgs.writeShellScriptBin "pi-pocket-trial-login" ''
    set -euo pipefail
    host=$(/usr/bin/tailscale ip -4)
    exec ${pkgs.nodejs_24}/bin/node --input-type=module - "$host" <<'JS'
    import { readFileSync } from 'node:fs';
    const { ownerToken } = JSON.parse(readFileSync(${builtins.toJSON "${privateHome}/.pi-pocket/config.json"}, 'utf8'));
    console.log('http://' + process.argv[2] + ':${toString port}/login?token=' + encodeURIComponent(ownerToken));
    JS
  '';
in {
  options.piPocketTrial.enable = lib.mkEnableOption "the isolated Pi Pocket trial on Omarchy";

  config = lib.mkIf cfg.enable {
    home.packages = [sandbox login];
    home.file = {
      ".local/bin/pi-pocket-trial-login".source = "${login}/bin/pi-pocket-trial-login";
      ".local/bin/pi-pocket-trial-sandbox".source = "${sandbox}/bin/pi-pocket-trial-sandbox";
      # Only nonsecret routing belongs in the store. The deliberately provisioned
      # personal gateway client key stays in private trial state, not auth.json
      # from another profile. No management key or upstream OAuth is exposed.
      ".local/state/pi-pocket-trial/home/.config/pi-pocket-trial/models.json".text = builtins.toJSON {
        providers.subscription-codex = {
          baseUrl = "http://${config.subscriptionProxy.address}:8317/v1";
          api = "openai-responses";
          authHeader = true;
          apiKey = "!${pkgs.coreutils}/bin/cat ${profile}/proxy-client-key";
          models =
            map (model: {
              inherit (model) id name;
              reasoning = true;
              input = ["text"];
              contextWindow = 128000;
              maxTokens = 32000;
              cost = {
                input = 0;
                output = 0;
                cacheRead = 0;
                cacheWrite = 0;
              };
            }) [
              {
                id = "gpt-6-luna";
                name = "Codex 6 Luna (personal proxy)";
              }
              {
                id = "gpt-6.1-sol";
                name = "Codex 6.1 Sol (personal proxy)";
              }
              {
                id = "gpt-6-astra";
                name = "Codex 6 Astra (personal proxy)";
              }
            ];
        };
      };
      ".local/state/pi-pocket-trial/home/.config/pi-pocket-trial/AGENTS.md".text = ''
        You are John's isolated Pi Durable trial, not the production assistant.
        Always respond in English. Your default directory is /home/pi-pocket/notes
        (~/notes), a read/write mount of John's actual notes project. John has
        authorized project edits; follow its vault editing rules, locking and
        readback. The existing host auto-commit process is unchanged; do not
        commit, merge or push unless John separately asks you to.
        /search food [--nutrition] <query> is a deterministic read-only mise task.
        /food <entry> runs mise run log-food through a one-off local-food helper
        using the trial's subscription-codex/gpt-6-luna model. Do not log it twice
        or invoke /food recursively. A stopped/interrupted command may already
        have written: inspect the daily note before a retry, never blindly replay.
        VAULT_DIR, VAULT_NAME and VLT_VAULT all name /home/pi-pocket/notes.
        Use vlt vault="$VAULT_NAME" rather than vault="Personal" in this sandbox;
        there is no host Obsidian registry. Existing tasks use VAULT_NAME.
        Use /home/pi-pocket/scratch for temporary generated files only.
        Hermes state and other agent profiles are not mounted. Do not try to
        recover or connect to them over the network.
        No Telegram, email, calendar, production jobs, or other external mutations
        are authorized. Explain missing integrations rather than claiming parity.
        Never read or display credentials, Pi Pocket's owner token, or auth files.
        Ask before installing extensions, scheduling work, or changing app settings.
      '';
    };
    xdg.configFile."pi-pocket-trial/deployment.json".text = builtins.toJSON {
      schemaVersion = 1;
      version = package.version;
      inherit (package) revision piVersion;
      inherit state privateHome sandboxHome profile data workspace port notesSource;
      notesReadOnly = false;
      package = toString package;
      service = "pi-pocket-trial.service";
      access = "Tailscale IPv4 only; HTTP inside the encrypted tailnet";
      authentication = "Personal subscription proxy client key only; upstream OAuth remains outside the trial";
      networkIsolation = false;
    };
    home.activation.piPocketTrialDirectories = lib.hm.dag.entryBetween ["reloadSystemd"] ["linkGeneration"] ''
      run ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArgs [
        state
        privateHome
        "${privateHome}/scratch"
        "${privateHome}/notes"
        "${privateHome}/.pi-pocket"
        "${privateHome}/.cache"
        "${privateHome}/.local/share"
        "${privateHome}/.local/state"
        "${privateHome}/.config/pi-pocket-trial"
        "${privateHome}/.config/claude-personal"
      ]}
    '';
    systemd.user.services.pi-pocket-trial = {
      Unit = {
        Description = "Isolated Pi Pocket / Pi Durable browser trial";
        After = ["network-online.target"];
        StartLimitIntervalSec = 0;
      };
      Service = {
        Type = "simple";
        ExecStart = launcher;
        WorkingDirectory = state;
        UMask = "0077";
        Restart = "always";
        RestartSec = 5;
        TimeoutStopSec = 30;
        NoNewPrivileges = true;
        KillMode = "control-group";
      };
      Install.WantedBy = ["default.target"];
    };
  };
}
