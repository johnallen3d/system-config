{pkgs, ...}: let
  # Pi packages to install globally
  piPackages = [
    "pi-prompt-template-model"
    "pi-subagents" 
    "@tmustier/pi-skill-creator"
  ];
  
  # Create install script for pi packages — uses @latest so packages track pi
  installPiPackages = pkgs.writeShellScript "install-pi-packages" ''
    for package in ${toString piPackages}; do
      ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@latest install npm:$package 2>/dev/null || true
    done
  '';
in
pkgs.writeShellScriptBin "pi" ''
  export PI_CODING_AGENT_DIR="$HOME/.config/pi"

  # Refresh pi packages once per day
  marker="$HOME/.config/pi/packages-installed"
  today=$(${pkgs.coreutils}/bin/date +%Y-%m-%d)
  if [ ! -f "$marker" ] || [ "$(${pkgs.coreutils}/bin/cat "$marker")" != "$today" ]; then
    ${installPiPackages}
    echo "$today" > "$marker"
  fi

  exec ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@latest "$@"
''
