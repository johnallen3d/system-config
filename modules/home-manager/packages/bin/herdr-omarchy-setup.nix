{pkgs, ...}:
pkgs.writeShellScriptBin "herdr-omarchy-setup" ''
  set -euo pipefail
  case "''${1:-}" in
    --help|-h) echo 'Usage: herdr-omarchy-setup (seed session-scoped Omarchy, Miller, and Drummer connections)'; exit 0 ;;
    "") ;;
    *) echo 'Usage: herdr-omarchy-setup' >&2; exit 2 ;;
  esac
  # Home Manager activation has a minimal PATH; Herdr invokes ssh by name.
  # On macOS use Apple SSH: Nix OpenSSH rejects the Keychain options in ~/.ssh/config.
  export PATH=${
    if pkgs.stdenv.hostPlatform.isDarwin
    then "/usr/bin"
    else "${pkgs.openssh}/bin"
  }:$PATH
  herdr=${pkgs.herdr}/bin/herdr
  status=0
  # Omarchy (Arch) hosts, as "label target".
  for machine in "Omarchy johna@omarchy" "Miller johna@miller" "Drummer johna@drummer"; do
    label=''${machine%% *}
    target=''${machine#* }
    for local_session in personal work; do
      # Preserve existing personal panes on the host's managed default server.
      # Work uses its own remote server, not a second view of those panes.
      remote_session=default
      if [ "$local_session" = work ]; then remote_session=work; fi
      profiles="$($herdr --session "$local_session" machine list --json)"
      if printf '%s' "$profiles" | ${pkgs.jq}/bin/jq -e --arg label "$label" 'any(.[]; .label == $label)' >/dev/null; then
        # Preserve the opaque ID and all unrelated profiles. Do not silently
        # retarget an existing label or re-enable a user-disabled connection.
        printf '%s' "$profiles" | ${pkgs.jq}/bin/jq -e --arg label "$label" --arg target "$target" --arg remote "$remote_session" \
          'any(.[]; .label == $label and .target == $target and .session == $remote)' >/dev/null || {
          echo "Existing $label label in $local_session points elsewhere; review herdr --session $local_session machine list." >&2
          status=1
          continue
        }
        echo "$label machine profile already configured in $local_session."
      else
        # Noninteractive: never approve installation/replacement or stop a server.
        $herdr --session "$local_session" machine add "$target" \
          --label "$label" --remote-session "$remote_session" </dev/null || status=1
      fi
    done
  done
  exit "$status"
''
