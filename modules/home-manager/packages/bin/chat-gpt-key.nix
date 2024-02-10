{
  pkgs,
  brew_bin,
  ...
}:
pkgs.writeShellScriptBin "chat-gpt-key" ''
  ${brew_bin}/op item get ChatGPT --fields label=secret-key-nvim
''
