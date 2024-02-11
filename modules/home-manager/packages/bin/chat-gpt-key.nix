{
  pkgs,
  op_path,
  ...
}:
pkgs.writeShellScriptBin "chat-gpt-key" ''
  ${op_path} item get ChatGPT --fields label=secret-key-nvim
''
