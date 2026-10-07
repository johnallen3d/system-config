{pkgs, ...}:
pkgs.writeShellScriptBin "herdr-omarchy-setup" ''
  set -euo pipefail
  herdr=${pkgs.herdr}/bin/herdr
  profiles="$($herdr machine list --json)"
  if printf '%s' "$profiles" | ${pkgs.jq}/bin/jq -e 'any(.[]; .label == "Omarchy")' >/dev/null; then
    # Preserve the opaque ID and all unrelated profiles. Do not silently
    # retarget an existing label or re-enable a user-disabled connection.
    printf '%s' "$profiles" | ${pkgs.jq}/bin/jq -e \
      'any(.[]; .label == "Omarchy" and .target == "johna@omarchy" and .session == "default")' >/dev/null || {
      echo 'Existing Omarchy label points elsewhere; review herdr machine list.' >&2
      exit 1
    }
    echo 'Omarchy machine profile already configured.'
  else
    # Noninteractive: never approve installation/replacement or stop a server.
    # Omarchy Home Manager must already have started its compatible server.
    $herdr machine add johna@omarchy --label Omarchy --remote-session default </dev/null
  fi
''
