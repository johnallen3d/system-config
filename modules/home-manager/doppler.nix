# Manage non-secret Doppler settings; authentication remains writable and host-local.
{
  config,
  lib,
  pkgs,
  ...
}: let
  home = config.home.homeDirectory;
  endpoints = {
    api-host = "https://api.doppler.com";
    dashboard-host = "https://dashboard.doppler.com";
  };
  project = name: environment: {
    project = name;
    config = environment;
  };
  scopes = {
    "/" = endpoints;
    "${home}/dev/src/amfaro/calc" = project "calc" "dev";
    "${home}/dev/src/amfaro/cookbook" = project "shared" "dev";
    "${home}/dev/src/amfaro/dataops" = project "dataops" "dev";
    "${home}/dev/src/amfaro/docs" = project "shared" "prod";
    "${home}/dev/src/amfaro/global-catalog" = project "global-catalog" "dev";
    "${home}/dev/src/playground/home-assistant" = endpoints // project "home-assistant" "prod";
    "${home}/dev/src/playground/music-library" = endpoints // project "music-library" "dev";
    "${home}/dev/src/playground/pi-cielo" = endpoints // project "pi-cielo" "prod";
    "${home}/dev/src/system-config" = project "system-config" "dev_personal";
    "${home}/notes" = endpoints // project "notes" "prd";
  };
  setScopes = lib.concatStringsSep "\n" (lib.mapAttrsToList (scope: settings: ''
    ${lib.getExe pkgs.doppler} --no-read-env --no-check-version --silent \
      --config-dir "$tmp" configure set \
      ${lib.escapeShellArgs (lib.mapAttrsToList (key: value: "${key}=${value}") settings)} \
      --scope ${lib.escapeShellArg scope}
  '') scopes);
  manageSettings = pkgs.writeShellApplication {
    name = "doppler-managed-settings";
    runtimeInputs = [pkgs.coreutils pkgs.yq-go];
    text = ''
      umask 077
      dir=${lib.escapeShellArg "${home}/.doppler"}
      file="$dir/.doppler.yaml"
      if [[ -L "$dir" || -L "$file" ]]; then
        echo 'Refusing to update symlinked Doppler credential storage.' >&2
        exit 1
      fi
      install -d -m 0700 "$dir"
      tmp="$(mktemp -d "$dir/.managed-settings.XXXXXX")"
      trap 'rm -rf "$tmp"' EXIT
      if [[ -e "$file" ]]; then
        cp "$file" "$tmp/original.yaml"
        chmod 0600 "$tmp/original.yaml"
      fi

      # Generate only declared fields with Doppler's own setter/schema.
      # Its serializer drops unknown fields, so never give it the original file.
      ${setScopes}
      if [[ -e "$tmp/original.yaml" ]]; then
        yq eval-all -o=yaml 'select(fileIndex == 0) * (select(fileIndex == 1) | {"scoped": .scoped}) | ... style=""' \
          "$tmp/original.yaml" "$tmp/.doppler.yaml" > "$tmp/merged.yaml"
      else
        yq '{"scoped": .scoped}' "$tmp/.doppler.yaml" > "$tmp/merged.yaml"
      fi
      # Original tokens stay on this host, never in the Nix store or logs.

      # Remove only the retired Supacode Doppler scopes, including their local
      # token association. This does not revoke tokens or alter the application.
      export SUPACODE_SCOPE=${lib.escapeShellArg "${home}/.supacode/repos"}
      yq -i '.scoped |= with_entries(select(.key != strenv(SUPACODE_SCOPE) and (.key | split(strenv(SUPACODE_SCOPE) + "/") | .[0] != "")))' \
        "$tmp/merged.yaml"
      chmod 0600 "$tmp/merged.yaml"
      if [[ -e "$tmp/original.yaml" ]]; then
        if ! cmp -s "$file" "$tmp/original.yaml"; then
          echo 'Doppler state changed during activation; refusing to overwrite it.' >&2
          exit 1
        fi
      elif [[ -e "$file" || -L "$file" ]]; then
        echo 'Doppler state appeared during activation; refusing to overwrite it.' >&2
        exit 1
      fi
      if ! cmp -s "$file" "$tmp/merged.yaml"; then
        mv "$tmp/merged.yaml" "$file"
      fi
      chmod 0600 "$file"
    '';
  };
in {
  home.packages = [pkgs.doppler];
  home.activation.dopplerManagedSettings = lib.hm.dag.entryAfter ["writeBoundary"] ''
    if [ -z "''${DRY_RUN:-}" ]; then
      ${lib.getExe manageSettings}
    fi
  '';
}
