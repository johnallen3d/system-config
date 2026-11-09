# Switchyard, the Rex float tools (one Cargo workspace in ./switchyard):
#
# - rex-tab-picker: the cmd+k picker for tabs, agents (also cmd+i) and ended
#   tasks (../dotfiles/config/rex/actions/tab-picker.lua).
# - rex-spawn: the new-session picker (actions/new.lua), which opens a plain
#   session in a zoxide folder (cmd+shift+n) or starts agent work in a new
#   worktree of a catalog project (ctrl+cmd+n) on a chosen host. Its
#   --launch and --run modes do the work, and it holds the task registry and
#   actions behind the tab picker's tasks.
#
# The floats run on whichever host the focused session lives on, and
# rex-spawn's --run mode runs in the new tab on the target host, so this is
# installed on every host even though the Rex config is Mac-only. The
# palette, project catalog and dev hosts are read at runtime from the config
# file ./switchyard-config.nix writes; import that wherever this is installed.
{pkgs}: let
  inherit (pkgs) lib;
in
  pkgs.rustPlatform.buildRustPackage {
    pname = "switchyard";
    version = "0.1.0";
    src = lib.cleanSourceWith {
      src = ./switchyard;
      filter = path: _: baseNameOf path != "target";
    };
    cargoLock.lockFile = ./switchyard/Cargo.lock;
    nativeBuildInputs = [pkgs.makeWrapper];
    postInstall = ''
      # The picker lists this host's folders with zoxide; rex and ssh stay the
      # caller's.
      wrapProgram $out/bin/rex-spawn --prefix PATH : ${lib.makeBinPath [pkgs.zoxide]}
    '';
    meta.mainProgram = "rex-spawn";
  }
