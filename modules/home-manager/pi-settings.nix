# Pi agent settings managed declaratively.
#
# ~/.config/pi/settings.json is writable at runtime (pi updates lastChangelogVersion etc.)
# so we use home.activation with a jq merge instead of a read-only home.file symlink.
#
# Strategy: on every rebuild, overlay our desired settings on top of whatever pi wrote,
# preserving volatile fields (lastChangelogVersion, packages).
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
  jq = "${pkgs.jq}/bin/jq";

  mkPiSettingsActivation = settingsFile: settings: ''
    nixSettings='${builtins.toJSON settings}'
    mkdir -p "$(dirname "${settingsFile}")"
    if [ -f "${settingsFile}" ]; then
      merged=$(${jq} -s '.[0] * .[1]' "${settingsFile}" - <<< "$nixSettings")
      echo "$merged" > "${settingsFile}"
    else
      echo "$nixSettings" > "${settingsFile}"
    fi
  '';

  piModels = {
    providers.ollama = {
      baseUrl = "http://localhost:11434/v1";
      api = "openai-completions";
      apiKey = "ollama";
      compat = {
        supportsDeveloperRole = false;
        supportsReasoningEffort = false;
      };
      models = [
        {
          id = "gemma4:31b";
          name = "Gemma 4 31B (Ollama)";
          reasoning = false;
          input = ["text"];
          contextWindow = 128000;
          maxTokens = 8192;
        }
        {
          id = "qwen3-coder:30b";
          name = "Qwen 3 Coder 30B (Ollama)";
          reasoning = false;
          input = ["text"];
          contextWindow = 262144;
          maxTokens = 8192;
        }
      ];
    };
  };

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

  piSystemMd = ''
    - My name is John
    - My birthday is 1976-05-31
    - `@ollama/pi-web-search` currently registers `web_search` and `web_fetch`.
    - Prefer `web_search` for ordinary web search.
    - Prefer `web_fetch` for fetching a single web page.
    - If `pi-web-access` is re-enabled later, revisit these tool-preference instructions because tool names will conflict again.
  '';

  piWorkSystemMd = ''
    - My name is John Allen
    - I work for gmatter
    - I'm a software architect with additional devops responsibilities
    - `@ollama/pi-web-search` currently registers `web_search` and `web_fetch`.
    - Prefer `web_search` for ordinary web search.
    - Prefer `web_fetch` for fetching a single web page.
    - If `pi-web-access` is re-enabled later, revisit these tool-preference instructions because tool names will conflict again.
  '';

  piSettings = {
    defaultProvider = "openai-codex";
    defaultModel = "gpt-5.4";
    compaction.enabled = false;
    theme = "tokyo-night-storm";
    quietStartup = true;
  };

  piWorkSettings = {
    defaultProvider = "openai-codex";
    defaultModel = "gpt-5.4";
    compaction.enabled = false;
    theme = "tokyo-night-storm";
    quietStartup = true;
  };
in {
  home.activation.piSystemMd = lib.hm.dag.entryAfter ["writeBoundary"] ''
        mkdir -p "$HOME/.config/pi" "$HOME/.config/pi-work"
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

  home.activation.piModels = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi/models.json" piModels
  );

  home.activation.piWorkModels = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-work/models.json" piModels
  );

  home.activation.piClaudeBridgeSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi/claude-bridge.json" claudeBridgeSettings
  );

  home.activation.piWorkClaudeBridgeSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-work/claude-bridge.json" claudeBridgeSettings
  );

  # home.file handles all extension symlinks (nix store paths) for both contexts.
  # Themes are identical so pi-work just symlinks to the personal themes dir.
  home.activation.piWorkLinks = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ln -sfn "$HOME/.config/pi/themes" "$HOME/.config/pi-work/themes"
  '';
}
