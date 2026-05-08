{pkgs, ...}: let
  # Pi packages to install globally
  piPackages = [
    "context-mode"
    "pi-intercom"
    "pi-prompt-template-model"
    "pi-subagents"
    "@samfp/pi-memory"
    "@tmustier/pi-skill-creator"
  ];

  piVersion = "0.74.0";
  piPackage = pkgs.buildNpmPackage {
    pname = "pi-coding-agent";
    version = piVersion;
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@earendil-works/pi-coding-agent/-/pi-coding-agent-${piVersion}.tgz";
      hash = "sha256-l0pzuWGVvX1jDhFYaey14N16XDo47kkm3JlEhmPUo0Q=";
    };
    sourceRoot = "package";
    npmDepsHash = "sha256-StlM0oonufxSMbkbLTg4Clh5tHCTOMCSh0GE4BVLJIQ=";
    dontNpmBuild = true;
    postPatch = ''
      cp ${./pi-package-lock.json} package-lock.json
    '';
  };

  # Create install script for pi packages using managed pi binary, not transient npx cache
  installPiPackages = pkgs.writeShellScript "install-pi-packages" ''
    for package in ${toString piPackages}; do
      ${piPackage}/bin/pi install npm:$package 2>/dev/null || true
    done
  '';
in
pkgs.writeShellScriptBin "pi" ''
  # Strip transient npx shims inherited from older installs so managed pi wins.
  cleaned_path=""
  IFS=':' read -r -a path_entries <<< "$PATH"
  for entry in "''${path_entries[@]}"; do
    if [[ "$entry" =~ /\.npm/_npx/[^/]+/node_modules/\.bin$ ]]; then
      continue
    fi
    if [ -n "$cleaned_path" ]; then
      cleaned_path="$cleaned_path:$entry"
    else
      cleaned_path="$entry"
    fi
  done
  export PATH="$cleaned_path"

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

  exec ${piPackage}/bin/pi "$@"
''
