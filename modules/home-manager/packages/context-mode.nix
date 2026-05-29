{pkgs, ...}:
# context-mode's upstream has a stale package-lock.json and native deps
# (better-sqlite3) that make buildNpmPackage fragile. Prefer the Pi-managed
# install for the active profile; fall back to an ephemeral latest npx run.
pkgs.writeShellScriptBin "context-mode" ''
  profile_dir="''${PI_CODING_AGENT_DIR:-$HOME/.config/pi}"
  package_dir="$profile_dir/npm/node_modules/context-mode"
  cli="$package_dir/cli.bundle.mjs"

  if [ -f "$cli" ]; then
    exec ${pkgs.nodejs_24}/bin/node "$cli" "$@"
  fi

  exec ${pkgs.nodejs_24}/bin/npx --yes context-mode@latest "$@"
''
