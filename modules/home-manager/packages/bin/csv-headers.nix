{pkgs, ...}:
pkgs.writeShellScriptBin "csv-headers" ''
  ${pkgs.coreutils}/bin/head -n 1 "$1" | ${pkgs.coreutils}/bin/tr ',' '\n'
''
