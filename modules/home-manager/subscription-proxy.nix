{
  cliproxyModels,
  cliproxyPanel,
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
  # The official panel and model catalog are flake inputs: locked, served from
  # the store, and bumped by `mise update-system` with everything else. The
  # panel's own auto-update stays off.
  panel = pkgs.runCommand "subscription-proxy-management-center" {} ''
    mkdir -p "$out"
    ln -s ${cliproxyPanel} "$out/management.html"
  '';
  proxy = pkgs.cliproxyapi;
  # Upstream router-for-me/models only defines gemini-4-neon-xhigh for the
  # antigravity channel (and labels it "Gemini 4 Neon"). Expose all four
  # upstream Neon effort variants with distinct display names so agy enables
  # /effort and avoids label collisions with the bare gemini-4-neon alias.
  modelCatalog = pkgs.runCommand "subscription-proxy-models.json" {} ''
    ${pkgs.python3}/bin/python3 - ${cliproxyModels}/models.json "$out" <<'EOF'
    import copy, json, sys
    src, dst = sys.argv[1], sys.argv[2]
    data = json.loads(open(src).read())
    antigravity = data.get("antigravity", [])
    by_id = {m.get("id"): m for m in antigravity if isinstance(m, dict)}
    base = copy.deepcopy(by_id.get("gemini-4-neon-xhigh"))
    if base is None:
        raise SystemExit("subscription-proxy: gemini-4-neon-xhigh missing from cliproxyModels")
    variants = (
        ("gemini-4-neon-low", "Gemini 4 Neon (Low)"),
        ("gemini-4-neon-medium", "Gemini 4 Neon (Medium)"),
        ("gemini-4-neon-high", "Gemini 4 Neon (High)"),
        ("gemini-4-neon-xhigh", "Gemini 4 Neon (XHigh)"),
    )
    for model_id, label in variants:
        if model_id in by_id:
            by_id[model_id]["display_name"] = label
            by_id[model_id]["description"] = label
        else:
            entry = copy.deepcopy(base)
            entry["id"] = model_id
            entry["name"] = model_id
            entry["display_name"] = label
            entry["description"] = label
            antigravity.append(entry)
    with open(dst, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    EOF
  '';
  template = pkgs.writeText "subscription-proxy-server.json" (builtins.toJSON {
    host = cfg.address;
    catalog = modelCatalog;
    ports = {
      personal = 8317;
      work = 8318;
    };
  });
  endpoints = {
    personal = "http://${cfg.address}:8317";
    work = "http://${cfg.address}:8318";
  };
  # Curated work Claude/Codex lineup, shared by Mac and Omarchy.
  workClaudeSettings = pkgs.writeText "subscription-proxy-work-claude.json" (builtins.toJSON {
    env = {
      ANTHROPIC_DEFAULT_OPUS_MODEL = "claude-opus-5-5";
      ANTHROPIC_DEFAULT_SONNET_MODEL = "claude-sonnet-5-5";
      ANTHROPIC_DEFAULT_HAIKU_MODEL = "claude-haiku-5-5";
      ANTHROPIC_DEFAULT_FABLE_MODEL = "claude-fable-5-1";
    };
    modelPicker = {
      replaceBuiltInOptions = true;
      options = [
        {
          model = "claude-haiku-5-5";
          label = "Claude Haiku 5.5";
        }
        {
          model = "claude-opus-5-5";
          label = "Claude Opus 5.5";
        }
        {
          model = "claude-fable-5-1";
          label = "Claude Fable 5.1";
        }
        {
          model = "gpt-6-luna";
          label = "Codex 6 Luna";
        }
        {
          model = "gpt-6.1-sol";
          label = "Codex 6.1 Sol";
        }
        {
          model = "gpt-6-astra";
          label = "Codex 6 Astra";
        }
      ];
    };
  });
  # Personal Claude uses only the personal gateway: the paid Claude login, plus
  # Antigravity extras (AI Pro). Neon is the fallback default for new sessions.
  personalClaudeSettings = pkgs.writeText "subscription-proxy-personal-claude.json" (builtins.toJSON {
    env = {
      # A fallback, not a forced selection: /model choices survive new sessions.
      ANTHROPIC_DEFAULT_MODEL = "gemini-4-neon-xhigh";
      ANTHROPIC_SMALL_FAST_MODEL = "claude-haiku-5-5";
      ANTHROPIC_DEFAULT_OPUS_MODEL = "claude-opus-5-5";
      ANTHROPIC_DEFAULT_SONNET_MODEL = "claude-sonnet-5-5";
      ANTHROPIC_DEFAULT_HAIKU_MODEL = "claude-haiku-5-5";
      ANTHROPIC_DEFAULT_FABLE_MODEL = "claude-fable-5-1";
    };
    modelPicker = {
      replaceBuiltInOptions = true;
      # Non-native IDs borrow a known client capability profile. Gemini keeps
      # Sonnet 4.6's conservative 200k window, well under its 1M upstream limit.
      options = [
        {
          model = "gemini-4-neon-xhigh";
          label = "Gemini 4 Neon";
          behavesAs = "claude-sonnet-4-6";
        }
        {
          model = "gemini-4-hydrogen-xhigh";
          label = "Gemini 4 Hydrogen";
          behavesAs = "claude-sonnet-4-6";
        }
        {
          model = "claude-haiku-5-5";
          label = "Claude Haiku 5.5";
        }
        {
          model = "claude-sonnet-5-5";
          label = "Claude Sonnet 5.5";
        }
        {
          model = "claude-opus-5-5";
          label = "Claude Opus 5.5";
        }
        {
          model = "claude-fable-5-1";
          label = "Claude Fable 5.1";
        }
        {
          model = "claude-opus-5-5-high";
          label = "Claude Opus 5.5 High (Antigravity)";
          behavesAs = "claude-opus-5-5";
        }
        {
          model = "claude-sonnet-5-5-high";
          label = "Claude Sonnet 5.5 High (Antigravity)";
          behavesAs = "claude-sonnet-5-5";
        }
      ];
    };
  });
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
    workClaude.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Manage work Claude Code proxy routing and its curated model picker on every activation.";
    };
    personalClaude.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Manage personal Claude Code through the isolated personal Claude/Antigravity gateway.";
    };
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
          ${lib.getExe manager} configure-client --command ${lib.getExe manager} \
            ${lib.optionalString cfg.workClaude.enable "--claude-settings ${workClaudeSettings}"} \
            ${lib.optionalString cfg.personalClaude.enable "--personal-claude-settings ${personalClaudeSettings}"}
        fi
      '';
    home.activation.subscriptionProxyServer =
      lib.mkIf cfg.server.enable
      (lib.hm.dag.entryAfter ["linkGeneration"] ''
        if [ -z "''${DRY_RUN:-}" ]; then
          ${lib.getExe manager} seed-server --template ${template}
          # Tailnet-only HTTPS front of the personal proxy for agy, which rejects
          # remote plain HTTP. Persistent in tailscaled; other Serve ports untouched.
          if ! /usr/bin/tailscale serve --bg --https=8443 --yes "${endpoints.personal}" >/dev/null; then
            echo "subscription-proxy: could not publish the personal HTTPS endpoint (Tailscale Serve :8443)" >&2
          fi
          for profile in personal work; do
            if ${pkgs.systemd}/bin/systemctl --user is-active --quiet "subscription-proxy-$profile.service"; then
              ${lib.getExe manager} reload-catalog "$profile" --catalog ${modelCatalog}
            fi
          done
          if ${pkgs.systemd}/bin/systemctl --user is-active --quiet subscription-proxy-work.service; then
            ${lib.getExe manager} sync-go
          fi
        fi
      '');
    systemd.user.services = lib.mkIf cfg.server.enable {
      subscription-proxy-personal = service "personal";
      subscription-proxy-work = service "work";
    };
  };
}
