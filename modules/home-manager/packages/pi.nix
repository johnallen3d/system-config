{pkgs, ...}: let
  # Pi packages to install globally
  piPackages = [
    "pi-prompt-template-model"
    "pi-subagents"
    "@samfp/pi-memory"
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
  # Respect PI_CODING_AGENT_DIR if already set (e.g. by mise for work context);
  # otherwise fall back to personal config dir.
  if [ -z "$PI_CODING_AGENT_DIR" ]; then
    export PI_CODING_AGENT_DIR="$HOME/.config/pi"
  fi

  # Refresh pi packages once per day (tracked per agent dir)
  marker="$PI_CODING_AGENT_DIR/packages-installed"
  today=$(${pkgs.coreutils}/bin/date +%Y-%m-%d)
  if [ ! -f "$marker" ] || [ "$(${pkgs.coreutils}/bin/cat "$marker")" != "$today" ]; then
    ${installPiPackages}
    echo "$today" > "$marker"
  fi

  exec ${pkgs.nodejs_24}/bin/npx --yes @mariozechner/pi-coding-agent@latest "$@"
''
