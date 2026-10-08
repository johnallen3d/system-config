{
  pkgs,
  username,
  homeDir,
}: let
  shell = "${homeDir}/.nix-profile/bin/fish";
  setup = pkgs.writeShellScript "omarchy-fish-default-shell-root" ''
    set -euo pipefail
    if [ "$EUID" -ne 0 ]; then
      echo 'This account-level change requires sudo authorization.' >&2
      exit 1
    fi
    account_home=$(/usr/bin/getent passwd ${pkgs.lib.escapeShellArg username} | ${pkgs.coreutils}/bin/cut -d: -f6)
    if [ "$account_home" != ${pkgs.lib.escapeShellArg homeDir} ] || [ ! -x ${pkgs.lib.escapeShellArg shell} ]; then
      echo 'Refusing shell change: account home or managed Fish executable does not match.' >&2
      exit 1
    fi
    if ! ${pkgs.gnugrep}/bin/grep -Fxq -- ${pkgs.lib.escapeShellArg shell} /etc/shells; then
      printf '\n%s\n' ${pkgs.lib.escapeShellArg shell} >> /etc/shells
    fi
    /usr/bin/chsh -s ${pkgs.lib.escapeShellArg shell} ${pkgs.lib.escapeShellArg username}
    echo 'Fish is now the account default. Open a new terminal or SSH login.'
  '';
in
  pkgs.writeShellScriptBin "omarchy-fish-default-shell" ''
    set -euo pipefail
    wanted=${pkgs.lib.escapeShellArg shell}
    current=$(/usr/bin/getent passwd ${pkgs.lib.escapeShellArg username} | ${pkgs.coreutils}/bin/cut -d: -f7)
    if [ "$current" = "$wanted" ] && ${pkgs.gnugrep}/bin/grep -Fxq -- "$wanted" /etc/shells; then
      echo 'Fish is already the registered account default.'
      exit 0
    fi
    if [ "''${1:-}" = '--check' ]; then
      printf 'Account shell is %s; run omarchy-fish-default-shell to authorize Fish.\n' "$current" >&2
      exit 1
    fi
    if [ "$#" -ne 0 ]; then
      echo 'Usage: omarchy-fish-default-shell [--check]' >&2
      exit 2
    fi
    exec /usr/bin/sudo -- ${setup}
  ''
