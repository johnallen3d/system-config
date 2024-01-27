{pkgs, ...}:
pkgs.writeShellScriptBin "wav-to-mp3" ''
  for file in *.wav; do
    ffmpeg -i "$file" -codec:a libmp3lame -qscale:a 2 "''${file[@]/%wav/mp3}"
  done
''
