{pkgs, ...}:
pkgs.writeShellScriptBin "scratch" ''
  type="$1"
  path="$HOME/Dropbox/Notes/scratch"

  # if type is not blank
  if [ -n "$type" ]; then
    nvim "$path/scratch.$type"
  else
    id=$(${pkgs.coreutils}/bin/date '+%Y-%m-%d-%H-%M-%S')
    nvim "$path/scratch.$id.md"
  fi
''
