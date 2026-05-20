{pkgs, ...}: let
  lib = pkgs.lib;
  piPackages = import ../pi/packages.nix {inherit lib;};

  # Keep pi nix-managed as a wrapper, but let runtime resolve latest upstream
  # automatically so John does not have to bump piVersion manually.
  piPackageSpec = "@earendil-works/pi-coding-agent@latest";
  personalPackageStamp = builtins.hashString "sha256" (builtins.toJSON {
    runtime = piPackageSpec;
    packages = piPackages.personalPackageSpecs;
  });
  workPackageStamp = builtins.hashString "sha256" (builtins.toJSON {
    runtime = piPackageSpec;
    packages = piPackages.workPackageSpecs;
  });

  runPi = pkgs.writeShellScript "run-pi-latest" ''
    exec ${pkgs.nodejs_24}/bin/npx --yes ${piPackageSpec} "$@"
  '';

  # Install declared Pi packages with the same managed/latest pi runtime the
  # wrapper executes, not a separately pinned core binary.
  installPiPackages = pkgs.writeShellScript "install-pi-packages" ''
    for package in "$@"; do
      ${runPi} install "$package" 2>/dev/null || true
    done
  '';

  repairPiPackages = pkgs.writeShellScript "repair-pi-packages" ''
        node_modules_dir="$HOME/.local/lib/node_modules"

        skill_creator_dir="$node_modules_dir/@tmustier/pi-skill-creator"
        if [ -d "$skill_creator_dir" ] && [ -f "$skill_creator_dir/SKILL.md" ]; then
          mkdir -p "$skill_creator_dir/skill-creator"
          cp "$skill_creator_dir/SKILL.md" "$skill_creator_dir/skill-creator/SKILL.md"
          ${pkgs.python3}/bin/python - <<'PY'
    import json
    import os
    from pathlib import Path

    package_json = Path(os.path.expanduser("~/.local/lib/node_modules/@tmustier/pi-skill-creator/package.json"))
    if package_json.exists():
        data = json.loads(package_json.read_text())
        pi = data.setdefault("pi", {})
        if pi.get("skills") != ["./skill-creator"]:
            pi["skills"] = ["./skill-creator"]
            package_json.write_text(json.dumps(data, indent=2) + "\n")
    PY
        fi

        context_mode_dir="$node_modules_dir/context-mode"
        if [ -d "$context_mode_dir/skills" ]; then
          ${pkgs.python3}/bin/python - <<'PY'
    import json
    import os
    from pathlib import Path

    package_json = Path(os.path.expanduser("~/.local/lib/node_modules/context-mode/package.json"))
    skills_dir = Path(os.path.expanduser("~/.local/lib/node_modules/context-mode/skills"))
    if package_json.exists() and skills_dir.exists():
        data = json.loads(package_json.read_text())
        pi = data.setdefault("pi", {})
        skill_paths = sorted(
            f"./skills/{path.parent.name}"
            for path in skills_dir.glob("*/SKILL.md")
        )
        if skill_paths and pi.get("skills") != skill_paths:
            pi["skills"] = skill_paths
            package_json.write_text(json.dumps(data, indent=2) + "\n")
    PY
        fi
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

    if [ "$PI_CODING_AGENT_DIR" = "$HOME/.config/pi-work" ]; then
      expected_stamp='${workPackageStamp}'
      package_args=(${lib.escapeShellArgs piPackages.workPackageSpecs})
    else
      expected_stamp='${personalPackageStamp}'
      package_args=(${lib.escapeShellArgs piPackages.personalPackageSpecs})
    fi

    # Refresh pi packages whenever declared package set changes (tracked per agent dir)
    marker="$PI_CODING_AGENT_DIR/packages-installed"
    if [ ! -f "$marker" ] || [ "$(${pkgs.coreutils}/bin/cat "$marker")" != "$expected_stamp" ]; then
      ${installPiPackages} "''${package_args[@]}"
      echo "$expected_stamp" > "$marker"
    fi

    ${repairPiPackages}

    exec ${runPi} "$@"
  ''
