{pkgs, ...}:
pkgs.writeShellScriptBin "flac-to-mp3" ''
  for a in *.flac; do
    ${pkgs.ffmpeg}/bin/ffmpeg -i "$a" -vsync 2 -qscale:a 0 "''${a[@]/%flac/mp3}"
  done
''
