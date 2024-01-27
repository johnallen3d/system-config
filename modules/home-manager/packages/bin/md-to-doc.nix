{pkgs, ...}:
pkgs.writeShellScriptBin "md-to-doc" ''
  # usage: md-to-doc [filename]
  #
  # given a file `notes.md`
  # > md-to-doc notes
  # will output `notes.docx`

  file="$1"

  ${pkgs.pandoc}/bin/pandoc -s "''${file}.md" -o "''${file}.docx"
''
