# John's production assistant on Omarchy: Pi Pocket / Pi Durable with real notes
# read/write and no other agent profile mounts.
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.piPocket;
  homeDir = config.home.homeDirectory;
  package = import ./packages/pi-pocket.nix {inherit pkgs;};
  state = "${homeDir}/.local/state/pi-pocket";
  privateHome = "${state}/home";
  sandboxHome = "/home/pi-pocket";
  profile = "${sandboxHome}/.config/pi-pocket";
  data = "${sandboxHome}/.pi-pocket";
  notesSource = "${homeDir}/notes";
  workspace = "${sandboxHome}/notes";
  port = 8796;
  # Caddy on pi-01 reaches the app directly over the LAN; UFW restricts ingress.
  listenAddress = "192.168.4.26";
  publicUrl = "https://pi.jallen7usa.com";
  # Pinned vault task binaries (vlt, gog, heif-convert).
  vaultTools = import ./packages/vault-tools.nix {
    inherit pkgs;
    runtimePkgs = pkgs;
  };
  taskPython = pkgs.python313.withPackages (ps: [ps.pillow ps.pyyaml]);
  paddleocr = import ./packages/omarchy-paddleocr.nix {inherit pkgs;};
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
    if [ "$canonical" = "''${VAULT_DIR:-/nonexistent}/scripts/food-pick" ] \
      || [ "$canonical" = "''${VAULT_DIR:-/nonexistent}/.mise/tasks/common-foods-browser" ]; then
      exec ${taskPython}/bin/python3 -I "$canonical" "$@"
    fi
    exec ${pkgs.uv}/bin/uv run --script "$script" "$@"
  '';
  taskPath = lib.makeBinPath [
    helperPi
    helperUv
    taskPython
    vaultTools.gog
    vaultTools.vlt
    vaultTools.heif-convert
    paddleocr
    pkgs.tesseract
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
  # Pocket's own gog login: Calendar read/write and Gmail read-only scopes.
  gogHome = "${sandboxHome}/.config/gogcli";
  gogPassword = "${privateHome}/.config/gogcli/keyring-password";
  # An empty root with explicit mounts, not a writable host home with deny-list
  # exceptions. The host user bus, SSH/GPG sockets, credentials, /etc secrets,
  # other agent data and host processes are not visible. John authorized read/write
  # access to the whole notes project, not to the rest of the host filesystem.
  sandbox = pkgs.writeShellScriptBin "pi-pocket-sandbox" ''
    set -euo pipefail
    gog_password=""
    if [ -r ${lib.escapeShellArg gogPassword} ]; then
      gog_password="$(${pkgs.coreutils}/bin/cat ${lib.escapeShellArg gogPassword})"
    fi
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
      NOTES_HELPER_PROVIDER=subscription-codex NOTES_HELPER_MODEL=gpt-6-luna \
      NOTES_LABEL_TEXT_ONLY=1 \
      GOG_HOME=${gogHome} GOG_KEYRING_BACKEND=file \
      GOG_KEYRING_PASSWORD="$gog_password" \
      GOG_ENABLE_COMMANDS=auth,config,calendar,gmail \
      GOG_GMAIL_NO_SEND=1 GOG_TIMEZONE=America/New_York \
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
  initialize = pkgs.writeText "pi-pocket-initialize.mjs" ''
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
  launcher = pkgs.writeShellScript "pi-pocket-server" ''
    set -euo pipefail
    # Namespace-local PIDs cannot arbitrate other namespaces. Keep an additional
    # host-side lifetime lock before any app initialization or live SQLite open.
    exec 9>${lib.escapeShellArg "${state}/server.lock"}
    ${pkgs.util-linux}/bin/flock --nonblock 9
    ${sandbox}/bin/pi-pocket-sandbox ${pkgs.nodejs_24}/bin/node ${initialize}
    # Upstream prints the owner URL on startup. Keep the bearer token out of the
    # routine journal; retrieve it only deliberately with the login helper.
    ${sandbox}/bin/pi-pocket-sandbox \
      ${pkgs.nodejs_24}/bin/node ${app}/src/server/main.ts \
      --host ${listenAddress} --port ${toString port} --data ${data} --cwd ${workspace} \
      2>&1 | ${pkgs.gnused}/bin/sed -u -E \
        's@(https?://[^[:space:]]*/login[?]token=)[^[:space:]]+@\1[redacted]@g'
  '';
  login = pkgs.writeShellScriptBin "pi-pocket-login" ''
    set -euo pipefail
    exec ${pkgs.nodejs_24}/bin/node --input-type=module - <<'JS'
    import { readFileSync } from 'node:fs';
    const { ownerToken } = JSON.parse(readFileSync(${builtins.toJSON "${privateHome}/.pi-pocket/config.json"}, 'utf8'));
    console.log(${builtins.toJSON publicUrl} + '/login?token=' + encodeURIComponent(ownerToken));
    JS
  '';
in {
  options.piPocket.enable = lib.mkEnableOption "Pi Pocket, John's production assistant on Omarchy";

  config = lib.mkIf cfg.enable {
    home.packages = [sandbox login];
    # Without Telegram the brief only updates the daily note; output goes to the journal.
    systemd.user.services.pi-pocket-morning-brief = {
      Unit.Description = "Morning brief into today's daily note";
      Service = {
        Type = "oneshot";
        ExecStart = "${sandbox}/bin/pi-pocket-sandbox ${pkgs.coreutils}/bin/env MORNING_BRIEF_DELIVERY=stdout mise run morning-brief";
        WorkingDirectory = state;
        UMask = "0077";
        NoNewPrivileges = true;
      };
    };
    systemd.user.timers.pi-pocket-morning-brief = {
      Unit.Description = "Daily morning brief at 05:00";
      Timer = {
        OnCalendar = "*-*-* 05:00:00";
        Persistent = true;
      };
      Install.WantedBy = ["timers.target"];
    };
    home.file = {
      ".local/bin/pi-pocket-login".source = "${login}/bin/pi-pocket-login";
      ".local/bin/pi-pocket-sandbox".source = "${sandbox}/bin/pi-pocket-sandbox";
      # Only nonsecret routing belongs in the store. The deliberately provisioned
      # personal gateway client key stays in private Pocket state, not auth.json
      # from another profile. No management key or upstream OAuth is exposed.
      ".local/state/pi-pocket/home/.config/pi-pocket/models.json".text = builtins.toJSON {
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
      ".local/state/pi-pocket/home/.config/pi-pocket/AGENTS.md".text = ''
        You are John's personal assistant: Pi Durable on Omarchy.
        Always respond in English. Your default directory is /home/pi-pocket/notes
        (~/notes), a read/write mount of John's actual notes project. John has
        authorized project edits; follow its vault editing rules, locking and
        readback. The existing host auto-commit process is unchanged; do not
        commit, merge or push unless John separately asks you to.
        /search food [--nutrition] <query> is a deterministic read-only mise task.
        /food <entry> runs mise run log-food through a one-off local-food helper
        using Pocket's subscription-codex/gpt-6-luna model. Do not log it twice
        or invoke /food recursively. A stopped/interrupted command may already
        have written: inspect the daily note before a retry, never blindly replay.
        For package-label uploads, run mise run import-food-label -- <exact image paths>.
        That helper uses the same isolated proxy through NOTES_HELPER_PROVIDER /
        NOTES_HELPER_MODEL and authoritative OCR (NOTES_LABEL_TEXT_ONLY=1), not
        image attachments: these models are text-only. Incomplete or ambiguous
        product/serving/nutrition evidence must not write. Never log a meal merely
        because a label was uploaded.
        VAULT_DIR, VAULT_NAME and VLT_VAULT all name /home/pi-pocket/notes.
        Use vlt vault="$VAULT_NAME" rather than vault="Personal" in this sandbox;
        there is no host Obsidian registry. Existing tasks use VAULT_NAME.
        Use /home/pi-pocket/scratch for temporary generated files only.
        Other agent profiles are not mounted. Do not try to recover or connect
        to them over the network.
        Google through gog (google-workspace skill): jallen7usa@gmail.com has
        Gmail read-only and Google Calendar read/write; john.allen@gmatter.co has
        Gmail and Calendar read-only (never attempt work calendar changes).
        Other Google services are disabled. There is no Telegram.
        A 05:00 timer runs mise run morning-brief into the daily note.
        No other external mutations are authorized.
        Never read or display credentials, Pi Pocket's owner token, or auth files.
        Ask before installing extensions, scheduling work, or changing app settings.
      '';
    };
    xdg.configFile."pi-pocket/deployment.json".text = builtins.toJSON {
      schemaVersion = 1;
      version = package.version;
      inherit (package) revision piVersion;
      inherit state privateHome sandboxHome profile data workspace port notesSource;
      notesReadOnly = false;
      package = toString package;
      service = "pi-pocket.service";
      inherit listenAddress publicUrl;
      access = "Plain HTTP on the reserved LAN address; UFW permits pi-01 Caddy only";
      authentication = "Personal subscription proxy client key only; upstream OAuth remains outside Pocket";
      networkIsolation = false;
    };
    home.activation.piPocketDirectories = lib.hm.dag.entryBetween ["reloadSystemd"] ["linkGeneration"] ''
      run ${pkgs.coreutils}/bin/install -d -m 0700 ${lib.escapeShellArgs [
        state
        privateHome
        "${privateHome}/scratch"
        "${privateHome}/notes"
        "${privateHome}/.pi-pocket"
        "${privateHome}/.cache"
        "${privateHome}/.local/share"
        "${privateHome}/.local/state"
        "${privateHome}/.config/pi-pocket"
        "${privateHome}/.config/claude-personal"
        "${privateHome}/.config/gogcli"
      ]}
      # A locally generated file-keyring password for Pocket's own gog tokens;
      # never a copy of another runtime's password.
      if [ ! -e ${lib.escapeShellArg gogPassword} ]; then
        run ${pkgs.bash}/bin/bash -c ${lib.escapeShellArg "umask 077; ${pkgs.openssl}/bin/openssl rand -base64 32 > ${lib.escapeShellArg gogPassword}"}
      fi
    '';
    systemd.user.services.pi-pocket = {
      Unit = {
        Description = "Pi Pocket / Pi Durable assistant";
        # Preserve active conversations; activate a changed runtime deliberately.
        X-RestartIfChanged = false;
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
