{pkgs, ...}:
pkgs.writeShellScriptBin "herdr-omarchy-setup" ''
  set -euo pipefail
  case "''${1:-}" in
    --help|-h) echo 'Usage: herdr-omarchy-setup (seed session-scoped Omarchy connections)'; exit 0 ;;
    "") ;;
    *) echo 'Usage: herdr-omarchy-setup' >&2; exit 2 ;;
  esac
  # Home Manager activation has a minimal PATH; Herdr invokes ssh by name.
  export PATH=${pkgs.openssh}/bin:$PATH
  herdr=${pkgs.herdr}/bin/herdr
  for local_session in personal work; do
    # Preserve existing personal panes on Omarchy's managed default server.
    # Work uses its own remote server, not a second view of those panes.
    remote_session=default
    if [ "$local_session" = work ]; then remote_session=work; fi
    profiles="$($herdr --session "$local_session" machine list --json)"
    if printf '%s' "$profiles" | ${pkgs.jq}/bin/jq -e 'any(.[]; .label == "Omarchy")' >/dev/null; then
      # Preserve the opaque ID and all unrelated profiles. Do not silently
      # retarget an existing label or re-enable a user-disabled connection.
      printf '%s' "$profiles" | ${pkgs.jq}/bin/jq -e --arg remote "$remote_session" \
        'any(.[]; .label == "Omarchy" and .target == "johna@omarchy" and .session == $remote)' >/dev/null || {
        echo "Existing Omarchy label in $local_session points elsewhere; review herdr --session $local_session machine list." >&2
        exit 1
      }
      echo "Omarchy machine profile already configured in $local_session."
    else
      # Noninteractive: never approve installation/replacement or stop a server.
      $herdr --session "$local_session" machine add johna@omarchy \
        --label Omarchy --remote-session "$remote_session" </dev/null
    fi
  done
''
