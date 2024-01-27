{pkgs, ...}:
pkgs.writeShellScriptBin "fixup" ''
  if [ $# -eq 1 ]; then
    # if there is an argmuent assume a specific sha to fixup
    ${pkgs.git}/bin/git commit --fixup $1
  else
    # otherwise fixup the last (non-fixup) commit. avoids "fixup! fixup! ..."
    ${pkgs.git}/bin/git log --oneline --no-color --max-count 25 \
      | ${pkgs.gnugrep}/bin/grep -v fixup! \
      | ${pkgs.coreutils}/bin/head -n 1 \
      | ${pkgs.gawk}/bin/awk '{print $1}' \
      | ${pkgs.findutils}/bin/xargs git commit --fixup
  fi
''
