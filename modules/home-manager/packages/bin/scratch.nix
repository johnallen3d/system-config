{pkgs, ...}:
pkgs.writeShellScriptBin "scratch" ''
  type="$1"
  path="$HOME/Library/Mobile\ Documents/com~apple~CloudDocs/scratch"

  # if type is not blank
  if [ -n "$type" ]; then
    nvim "$path/scratch.$type"
  else
    id=$(${pkgs.coreutils}/bin/date '+%Y-%m-%d-%H-%M-%S')
    nvim "$path/scratch.$id.md"
  fi
''
