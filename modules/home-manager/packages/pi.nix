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
  notesPackageStamp = builtins.hashString "sha256" (builtins.toJSON {
    runtime = piPackageSpec;
    packages = piPackages.notesPackageSpecs;
  });
  runPi = pkgs.writeShellScript "run-pi-latest" ''
    ${pkgs.nodejs_24}/bin/npx --yes ${piPackageSpec} "$@"
  '';

  # Install declared Pi packages with the same managed/latest pi runtime the
  # wrapper executes, not a separately pinned core binary.
  installPiPackages = pkgs.writeShellScript "install-pi-packages" ''
    for package in "$@"; do
      ${runPi} install "$package" 2>/dev/null || true
    done
  '';

  repairHeadroom = pkgs.writeShellScript "repair-headroom" ''
    exec ${pkgs.python3}/bin/python ${../pi/repair-headroom.py}
  '';
  repairNotesTelegram = pkgs.writeShellScript "repair-notes-telegram" ''
        profile_dir="''${PI_CODING_AGENT_DIR:-$HOME/.config/pi}"
        # Telegram auto-connect is a notes-only integration. Do not patch retired
        # skill/context packages or touch another profile during personal/work launch.
        [ "$profile_dir" = "$HOME/.config/pi-notes" ] || exit 0
        telegram_extension="$profile_dir/git/github.com/badlogic/pi-telegram/index.ts"
          [ -f "$telegram_extension" ] || exit 0
          TELEGRAM_EXTENSION="$telegram_extension" ${pkgs.python3}/bin/python - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["TELEGRAM_EXTENSION"])
source = path.read_text()
old = """\tpi.on(\"session_start\", async (_event, ctx) => {
\t\tconfig = await readConfig();
\t\tawait mkdir(TEMP_DIR, { recursive: true });
\t\tupdateStatus(ctx);
\t});"""
new = """\tpi.on(\"session_start\", async (_event, ctx) => {
\t\tconfig = await readConfig();
\t\tawait mkdir(TEMP_DIR, { recursive: true });
\t\tawait startPolling(ctx);
\t\tupdateStatus(ctx);
\t});"""
if new not in source:
    if old not in source:
        raise SystemExit(f"Telegram auto-connect patch target changed: {path}")
    path.write_text(source.replace(old, new, 1))
PY
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
    elif [ "$PI_CODING_AGENT_DIR" = "$HOME/.config/pi-notes" ]; then
      expected_stamp='${notesPackageStamp}'
      package_args=(${lib.escapeShellArgs piPackages.notesPackageSpecs})
    else
      expected_stamp='${personalPackageStamp}'
      package_args=(${lib.escapeShellArgs piPackages.personalPackageSpecs})
      # `pi install` currently also registers git packages in this profile.
      # Keep notes-only Telegram from being auto-discovered by normal Pi.
      PROFILE_DIR="$PI_CODING_AGENT_DIR" ${pkgs.python3}/bin/python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["PROFILE_DIR"]) / "settings.json"
if path.exists():
    data = json.loads(path.read_text())
    packages = data.get("packages", [])
    filtered = [package for package in packages if package != "git:github.com/badlogic/pi-telegram"]
    if filtered != packages:
        data["packages"] = filtered
        path.write_text(json.dumps(data, indent=2) + "\n")
PY
    fi

    # Refresh packages when declarations change or a prior install did not register one.
    marker="$PI_CODING_AGENT_DIR/packages-installed"
    refresh_packages=false
    if [ ! -f "$marker" ] || [ "$(${pkgs.coreutils}/bin/cat "$marker")" != "$expected_stamp" ]; then
      refresh_packages=true
    else
      for package in "''${package_args[@]}"; do
        ${pkgs.gnugrep}/bin/grep -Fq "\"$package\"" "$PI_CODING_AGENT_DIR/settings.json" 2>/dev/null || {
          refresh_packages=true
          break
        }
      done
    fi
    if [ "$refresh_packages" = true ]; then
      ${installPiPackages} "''${package_args[@]}"
      echo "$expected_stamp" > "$marker"
    fi

    # pi-headroom 0.1.0 pipes proxy logs without reading them. Repair the selected
  # profile before extension loading; npm refreshes can replace this source.
  ${repairHeadroom} || exit $?
  ${repairNotesTelegram}

    exec ${runPi} "$@"
  ''
