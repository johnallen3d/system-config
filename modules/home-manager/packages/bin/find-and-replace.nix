{pkgs, ...}:
pkgs.writeShellScriptBin "find-and-replace" ''
  ${pkgs.ripgrep}/bin/rg --files-with-matches "''${1}" \
    | ${pkgs.findutils}/gin/xargs sed -i ''' "s/''${1}/''${2}/g"
''
