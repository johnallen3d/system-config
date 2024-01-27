{pkgs, ...}:
pkgs.writeShellScriptBin "chat-gpt-key" ''
  /opt/homebrew/bin/op item get ChatGPT --fields label=secret-key-nvim
''
