{pkgs, ...}: let
  # Pi packages to install globally
  piPackages = [
    "pi-prompt-template-model"
    "pi-subagents" 
    "@tmustier/pi-skill-creator"
  ];
  
  # Create install script for pi packages
  installPiPackages = pkgs.writeShellScript "install-pi-packages" ''
    for package in ${toString piPackages}; do
      ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@0.66.1 install npm:$package 2>/dev/null || true
    done
  '';
in
pkgs.writeShellScriptBin "pi" ''
  # Ensure pi packages are installed on first run
  if [ ! -f "$HOME/.pi/packages-installed" ]; then
    echo "Installing pi packages..."
    ${installPiPackages}
    touch "$HOME/.pi/packages-installed"
  fi
  
  exec ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@0.66.1 "$@"
''
