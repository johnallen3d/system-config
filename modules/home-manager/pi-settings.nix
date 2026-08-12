# Pi agent settings managed declaratively.
#
# ~/.config/pi/settings.json is writable at runtime (pi updates lastChangelogVersion etc.)
# so we use home.activation with a jq merge instead of a read-only home.file symlink.
#
# Strategy: on every rebuild, overlay our desired settings on top of whatever pi wrote,
# preserving volatile fields such as lastChangelogVersion while keeping selected keys
# declarative from nix.
#
# Two agent dirs:
#   ~/.config/pi        — personal Pi profile ↔ ~/.config/claude-personal
#   ~/.config/pi-work   — work Pi profile ↔ ~/.config/claude-gmatter
#
# Personal is the default PI_CODING_AGENT_DIR. Work is selected by per-project mise/env wiring.
# Claude usage/account data shown through claude-bridge should come from the matching Claude profile.
#
# Extensions and themes are shared — pi-work symlinks back to the personal dir so
# we only manage them in one place (pi-extensions.nix).
{
  config,
  pkgs,
  lib,
  ...
}: let
  piPackages = import ./pi/packages.nix {inherit lib;};
  managedTheme = import ./managed-theme.nix {inherit lib;};
  jq = "${pkgs.jq}/bin/jq";

  mkPiSettingsActivation = settingsFile: settings: ''
    nixSettings='${builtins.toJSON settings}'
    mkdir -p "$(dirname "${settingsFile}")"

    if [ -f "${settingsFile}" ] && ${jq} empty "${settingsFile}" >/dev/null 2>&1; then
      merged=$(${jq} -s '.[0] * .[1] | del(.mcpServers)' "${settingsFile}" - <<< "$nixSettings")
    else
      if [ -f "${settingsFile}" ]; then
        cp "${settingsFile}" "${settingsFile}.invalid.bak"
        echo "Warning: ${settingsFile} contained invalid JSON; backed it up to ${settingsFile}.invalid.bak and restored managed defaults." >&2
      fi
      merged="$nixSettings"
    fi

    tmp_file="${settingsFile}.tmp.$$"
    printf '%s\n' "$merged" > "$tmp_file"
    mv "$tmp_file" "${settingsFile}"
  '';

  claudeBridgeSettings = {
    askClaude = {
      enabled = true;
      allowFullMode = true;
      defaultIsolated = false;
      appendSkills = true;
    };
    provider = {
      strictMcpConfig = true;
      pathToClaudeCodeExecutable = "${config.home.homeDirectory}/.local/bin/claude";
    };
  };

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

  piSettings = {
    defaultProvider = "openai-codex";
    defaultModel = "gpt-5.6-terra";
    compaction.enabled = false;
    packages = piPackages.personalPackageSpecs;
    theme = managedTheme.activeTheme.name;
    quietStartup = true;
  };

  piWorkSettings = {
    defaultProvider = "openai-codex";
    defaultModel = "gpt-5.6-terra";
    compaction.enabled = false;
    packages = piPackages.workPackageSpecs;
    theme = managedTheme.activeTheme.name;
    quietStartup = true;
  };

  piNotesSettings = {
    packages = piPackages.notesPackageSpecs;
    theme = managedTheme.activeTheme.name;
    quietStartup = true;
  };
  jsonFormat = pkgs.formats.json {};
in {
  home.activation.piSystemMd = lib.hm.dag.entryAfter ["writeBoundary"] ''
        mkdir -p "$HOME/.config/pi" "$HOME/.config/pi-work" "$HOME/.config/pi-notes"
        cat > "$HOME/.config/pi/SYSTEM.md" <<'EOF'
    ${piSystemMd}
    EOF
        cat > "$HOME/.config/pi-work/SYSTEM.md" <<'EOF'
    ${piWorkSystemMd}
    EOF
  '';

  home.activation.piSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi/settings.json" piSettings
  );

  home.activation.piWorkSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-work/settings.json" piWorkSettings
  );

  home.activation.piNotesSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-notes/settings.json" piNotesSettings
  );

  home.activation.piClaudeBridgeSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi/claude-bridge.json" claudeBridgeSettings
  );

  home.activation.piWorkClaudeBridgeSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-work/claude-bridge.json" claudeBridgeSettings
  );

  home.file.".config/pi/mcp.json".source = jsonFormat.generate "pi-mcp.json" piMcpSettings;
  home.file.".config/pi-work/mcp.json".source = jsonFormat.generate "pi-work-mcp.json" piWorkMcpSettings;

  # home.file handles all extension symlinks (nix store paths) for both contexts.
  # Themes are identical so pi-work just symlinks to the personal themes dir.
  home.activation.piWorkLinks = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ln -sfn "$HOME/.config/pi/themes" "$HOME/.config/pi-work/themes"
  '';
}
