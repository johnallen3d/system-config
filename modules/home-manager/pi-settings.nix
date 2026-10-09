# Pi agent settings managed declaratively.
#
# Pi settings.json files stay writable because Pi updates settings at runtime.
# On every rebuild, replace configuration with Nix declarations and preserve only
# the explicitly allowed lastChangelogVersion bookkeeping field. Removing a Nix
# setting therefore removes it from JSON; interactive changes last until rebuild.
#
# Two agent dirs:
#   ~/.config/pi        — personal Pi profile ↔ ~/.config/claude-personal
#   ~/.config/pi-work   — work Pi profile ↔ ~/.config/claude-gmatter
#
# Personal is the default PI_CODING_AGENT_DIR. Work is selected by per-project mise/env wiring.
#
# Extensions are managed for each profile in pi-extensions.nix; work themes
# symlink back to the personal profile.
{
  pkgs,
  lib,
  ...
}: let
  piPackages = import ./pi/packages.nix {inherit lib;};
  managedTheme = import ./managed-theme.nix {inherit lib;};
  jq = "${pkgs.jq}/bin/jq";

  mkPiSettingsActivation = settingsFile: settings: ''
    if [ -n "''${DRY_RUN:-}" ]; then
      echo "Would update managed settings: ${settingsFile}"
    else
      nixSettings='${builtins.toJSON settings}'
      mkdir -p "$(dirname "${settingsFile}")"

      if [ -f "${settingsFile}" ] && ${jq} -e -s 'length == 1 and (.[0] | type == "object")' "${settingsFile}" >/dev/null 2>&1; then
        merged=$(${jq} -s '(.[0] | with_entries(select(.key == "lastChangelogVersion"))) * .[1]' "${settingsFile}" - <<< "$nixSettings")
      else
        if [ -f "${settingsFile}" ]; then
          cp "${settingsFile}" "${settingsFile}.invalid.bak"
          echo "Warning: ${settingsFile} contained invalid JSON settings; backed it up to ${settingsFile}.invalid.bak and restored managed defaults." >&2
        fi
        merged="$nixSettings"
      fi

      tmp_file="${settingsFile}.tmp.$$"
      printf '%s\n' "$merged" > "$tmp_file"
      mv "$tmp_file" "${settingsFile}"
    fi
  '';

  piMcpSettings = {
    mcpServers = {
      "mcp-server-doppler" = {
        command = "bash";
        args = [
          "-lc"
          "export DOPPLER_TOKEN=\"$(security find-generic-password -s 'doppler-work' -a 'john.allen' -w)\" && exec npx -y @dopplerhq/mcp-server"
        ];
      };
      "mcp-server-motherduck" = {
        command = "uvx";
        args = [
          "mcp-server-motherduck"
          "--db-path"
          ":memory:"
          "--read-write"
        ];
      };
      "headroom" = {
        "command" = "/Users/john.allen/.pi/headroom-venv/bin/headroom";
        "args" = [
          "mcp"
          "serve"
          "--proxy-url"
          "http://127.0.0.1:8787"
        ];
      };
    };
  };

  piWorkMcpSettings = {
    mcpServers = {
      doppler = {
        command = "npx";
        args = [
          "-y"
          "@dopplerhq/mcp-server"
        ];
      };
      "mcp-server-motherduck" = {
        command = "uvx";
        args = [
          "mcp-server-motherduck"
          "--db-path"
          ":memory:"
          "--read-write"
        ];
      };
      "cloudflare-api" = {
        url = "https://mcp.cloudflare.com/mcp";
      };
      "headroom" = {
        "command" = "/Users/john.allen/.pi/headroom-venv/bin/headroom";
        "args" = [
          "mcp"
          "serve"
          "--proxy-url"
          "http://127.0.0.1:8787"
        ];
      };
      calc = {
        url = "https://calc-mcp.fly.dev/mcp";
        headers = {
          "x-api-key" = "\${CALC_MCP_API_KEY}";
        };
      };
      "calc-local" = {
        url = "http://127.0.0.1:8080/mcp";
        headers = {
          "x-api-key" = "hello-world";
        };
      };
    };
  };

  # Linux has no macOS Keychain or Mac-local headroom/calc services. Credentials
  # for subprocess MCP servers come from the selected launch environment.
  linuxMcpSettings = {
    mcpServers = {
      inherit (piMcpSettings.mcpServers) mcp-server-motherduck;
      mcp-server-doppler = piWorkMcpSettings.mcpServers.doppler;
    };
  };
  linuxWorkMcpSettings = {
    mcpServers = {
      inherit (piWorkMcpSettings.mcpServers) cloudflare-api doppler mcp-server-motherduck calc;
    };
  };

  piSystemMd = ''
    - ALWAYS RESPOND IN ENGLISH
    - My name is John
    - My birthday is 1976-05-31
    - NEVER FORGET ABOUT $PI_CODING_AGENT_DIR
  '';

  piWorkSystemMd = ''
    - ALWAYS RESPOND IN ENGLISH
    - My name is John Allen
    - I work for gmatter
    - I'm a software architect with additional devops responsibilities
    - NEVER FORGET ABOUT $PI_CODING_AGENT_DIR
  '';

  piCommonSettings = {
    defaultProvider = "openai-codex";
    defaultModel = "gpt-6.1-sol";
    compaction.enabled = false;
    theme = managedTheme.activeTheme.name;
    quietStartup = true;
    tuiMode = "fullscreen";
  };

  piPersonalUiSettings = {
    enableInstallTelemetry = false;
    collapseChangelog = true;
    showCacheMissNotices = true;
    terminal.showTerminalProgress = true;
    editorPaddingX = 1;
  };

  piSettings =
    piCommonSettings
    // piPersonalUiSettings
    // {
      defaultThinkingLevel = "high";
      packages = piPackages.personalPackageSpecs;
    };

  piWorkSettings =
    piCommonSettings
    // {
      defaultThinkingLevel = "high";
      defaultProjectTrust = "always";
      packages = piPackages.workPackageSpecs;
      subagents.agentOverrides = {
        context-builder = {
          model = "opencode-go/glm-5.2";
          thinking = "off";
        };
        delegate = {
          model = "opencode-go/glm-5.2";
          thinking = "medium";
        };
        oracle = {
          model = "opencode-go/kimi-k2.6";
          thinking = "high";
        };
        planner = {
          model = "opencode-go/glm-5.2";
          thinking = "medium";
        };
        researcher = {
          model = "opencode-go/glm-5.2";
          thinking = "low";
        };
        reviewer = {
          model = "opencode-go/kimi-k2.6";
          thinking = "high";
        };
        scout = {
          model = "opencode-go/deepseek-v4-flash";
          thinking = "off";
        };
        worker = {
          model = "opencode-go/glm-5.2";
          thinking = "medium";
        };
      };
    };

  piNotesSettings =
    piCommonSettings
    // piPersonalUiSettings
    // {
      defaultThinkingLevel = "medium";
      packages = piPackages.notesPackageSpecs;
    };
  jsonFormat = pkgs.formats.json {};
in {
  home.activation.piSystemMd = lib.hm.dag.entryAfter ["writeBoundary"] ''
    if [ -n "''${DRY_RUN:-}" ]; then
      echo "Would configure Pi profile instructions"
    else
        mkdir -p "$HOME/.config/pi" "$HOME/.config/pi-work" "$HOME/.config/pi-notes"
        cat > "$HOME/.config/pi/APPEND_SYSTEM.md" <<'EOF'
    ${piSystemMd}
    EOF
        # This module previously wrote these instructions as SYSTEM.md, replacing
        # Pi's native prompt. Remove only that known content, never a user override.
        if [ -f "$HOME/.config/pi/SYSTEM.md" ]; then
          if ${pkgs.diffutils}/bin/diff -q -w -B "$HOME/.config/pi/SYSTEM.md" "$HOME/.config/pi/APPEND_SYSTEM.md" >/dev/null; then
            rm "$HOME/.config/pi/SYSTEM.md"
          else
            echo "Warning: personal SYSTEM.md differs from the retired managed instructions; preserved user override." >&2
          fi
        fi
        cat > "$HOME/.config/pi-work/SYSTEM.md" <<'EOF'
    ${piWorkSystemMd}
    EOF
    fi
  '';

  home.activation.piSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi/settings.json" piSettings
  );

  home.activation.piWorkSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-work/settings.json" piWorkSettings
  );

  # The renamed package uses a new Pi git cache key. Drop only the old work
  # checkout once the managed package list no longer references it.
  home.activation.piAgentKitMigration = lib.hm.dag.entryAfter ["piWorkSettings"] ''
    if ! ${jq} -e '.packages | index("git:github.com/amfaro/pi-workflows")' "$HOME/.config/pi-work/settings.json" >/dev/null; then
      $DRY_RUN_CMD rm -rf "$HOME/.config/pi-work/git/github.com/amfaro/pi-workflows"
    fi
  '';

  home.activation.piNotesSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-notes/settings.json" piNotesSettings
  );

  # Remove files written by the retired integration, including the notes link.
  home.activation.piClaudeBridgeCleanup = lib.hm.dag.entryAfter ["writeBoundary"] ''
    if [ -n "''${DRY_RUN:-}" ]; then
      echo "Would remove retired Claude Bridge configuration"
    else
      rm -f "$HOME/.config/pi/claude-bridge.json" \
        "$HOME/.config/pi-work/claude-bridge.json" \
        "$HOME/.config/pi-notes/claude-bridge.json"
    fi
  '';

  # Personal uses Pi 1.x's built-in MCP (codemode exposure by default). The
  # work agent-kit owns its MCP integration; leave its configuration unchanged.
  home.file.".config/pi/mcp.json".source = jsonFormat.generate "pi-mcp.json" (
    if pkgs.stdenv.hostPlatform.isDarwin
    then piMcpSettings
    else linuxMcpSettings
  );
  home.file.".config/pi-work/mcp-adapter.json".source = jsonFormat.generate "pi-work-mcp-adapter.json" (
    if pkgs.stdenv.hostPlatform.isDarwin
    then piWorkMcpSettings
    else linuxWorkMcpSettings
  );

  # home.file handles all extension symlinks (nix store paths) for both contexts.
  # Themes are identical so pi-work just symlinks to the personal themes dir.
  home.activation.piWorkLinks = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ln -sfn "$HOME/.config/pi/themes" "$HOME/.config/pi-work/themes"
  '';
}
