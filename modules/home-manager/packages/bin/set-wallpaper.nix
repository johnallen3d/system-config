{pkgs, ...}:
pkgs.writeShellScriptBin "set-wallpaper" ''
  osascript -e "tell application \"System Events\" to tell every desktop to set picture to \"$1\""
''
