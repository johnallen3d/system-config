# Pi agent settings managed declaratively.
#
# ~/.config/pi/settings.json is writable at runtime (pi updates lastChangelogVersion etc.)
# so we use home.activation with a jq merge instead of a read-only home.file symlink.
#
# Strategy: on every rebuild, overlay our desired settings on top of whatever pi wrote,
# preserving volatile fields (lastChangelogVersion, packages).
#
# Two agent dirs:
#   ~/.config/pi        — personal, anthropic provider (PI_CODING_AGENT_DIR default)
#   ~/.config/pi-work   — work (amfaro), copilot provider (set by mise in ~/dev/src/amfaro/mise.toml)
#
# Extensions and themes are shared — pi-work symlinks back to the personal dir so
# we only manage them in one place (pi-extensions.nix).
{
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

  # Personal — anthropic is default via ANTHROPIC_API_KEY env var.
  # No copilot auth here; keep it isolated to pi-work.
  piSettings = {
    defaultProvider = "openai-codex";
    defaultModel = "gpt-5.5";
    compaction.enabled = false;
    theme = "tokyo-night-storm";
    quietStartup = true;
  };

  # Work (amfaro) — copilot only, no anthropic key in this context.
  # Skills point at the shared amfaro skills repo.
  piWorkSettings = {
    defaultProvider = "github-copilot";
    defaultModel = "claude-sonnet-4.6";
    skills = ["~/dev/src/amfaro/skills"];
    compaction.enabled = false;
    theme = "tokyo-night-storm";
    quietStartup = true;
  };
in {
  home.activation.piSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi/settings.json" piSettings
  );

  home.activation.piWorkSettings = lib.hm.dag.entryAfter ["writeBoundary"] (
    mkPiSettingsActivation "$HOME/.config/pi-work/settings.json" piWorkSettings
  );

  # home.file handles all extension symlinks (nix store paths) for both contexts.
  # Themes are identical so pi-work just symlinks to the personal themes dir.
  home.activation.piWorkLinks = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ln -sfn "$HOME/.config/pi/themes" "$HOME/.config/pi-work/themes"
  '';
}
