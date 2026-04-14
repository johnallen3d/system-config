# Pi agent settings managed declaratively.
#
# ~/.pi/agent/settings.json is writable at runtime (pi updates lastChangelogVersion etc.)
# so we use home.activation with a jq merge instead of a read-only home.file symlink.
#
# Strategy: on every rebuild, overlay our desired settings on top of whatever pi wrote,
# preserving volatile fields (lastChangelogVersion, packages).
#
# Pi config lives at ~/.config/pi (XDG-style) via PI_CODING_AGENT_DIR set in pi.nix.
{pkgs, ...}: let
  # Desired settings — volatile fields (lastChangelogVersion, packages) are intentionally
  # omitted so pi can manage them freely.
  piSettings = {
    defaultProvider = "anthropic";
    defaultModel = "claude-sonnet-4-6";
    compaction = {
      enabled = false;
    };
    theme = "tokyo-night-storm";
    quietStartup = true;
  };

  piSettingsJson = builtins.toJSON piSettings;
in {
  home.activation.piSettings = let
    jq = "${pkgs.jq}/bin/jq";
  in ''
    settingsFile="$HOME/.config/pi/settings.json"
    nixSettings='${piSettingsJson}'

    # Ensure the directory exists (pi may not have run yet)
    mkdir -p "$(dirname "$settingsFile")"

    if [ -f "$settingsFile" ]; then
      # Merge: apply our desired keys on top of existing file so pi-managed
      # fields (lastChangelogVersion, packages, auth tokens, etc.) are preserved.
      merged=$(${jq} -s '.[0] * .[1]' "$settingsFile" - <<< "$nixSettings")
      echo "$merged" > "$settingsFile"
    else
      echo "$nixSettings" > "$settingsFile"
    fi
  '';
}
