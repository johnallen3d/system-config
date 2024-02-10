{pkgs, ...}:
pkgs.writeShellScriptBin "delete-branch" ''
  if [ $# -eq 0 ]; then
    branch="$(${pkgs.git}/bin/git rev-parse --abbrev-ref HEAD)"
  else
    branch="''$1"
  fi

  if ${pkgs.git}/bin/git branch | ${pkgs.gnugrep}/bin/grep --quiet config-changes; then
    default_branch="config-changes"
  else
    default_branch="$(${pkgs.git}/bin/git remote show origin | ${pkgs.gnused}/bin/sed -n '/HEAD branch/s/.*: //p')"
  fi

  ${pkgs.git}/bin/git checkout "$default_branch"
  ${pkgs.git}/bin/git pull
  ${pkgs.git}/bin/git push origin :"$branch"
  ${pkgs.git}/bin/git branch -D "$branch"
''
