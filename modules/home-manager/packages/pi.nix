{pkgs, ...}:
pkgs.writeShellScriptBin "pi" ''
  exec ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@0.66.1 "$@"
''
