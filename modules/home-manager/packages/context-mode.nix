{pkgs, ...}:
# context-mode's upstream has a stale package-lock.json and native deps
# (better-sqlite3) that make buildNpmPackage fragile. Use npx wrapper instead.
pkgs.writeShellScriptBin "context-mode" ''
  exec ${pkgs.nodejs_24}/bin/npx --yes context-mode@1.0.22 "$@"
''
