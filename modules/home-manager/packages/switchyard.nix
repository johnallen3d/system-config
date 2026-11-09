# Switchyard, the Rex float tools (one Cargo workspace in ./switchyard):
#
# - rex-tab-picker: the cmd+k tab picker (../dotfiles/config/rex/actions/tab-picker.lua).
# - rex-spawn: the ctrl+cmd+n spawn picker (actions/spawn.lua), which starts
#   agent work in a new worktree of a catalog project on a chosen dev host,
#   and the cmd+i task inbox (actions/inbox.lua), also as rex-inbox.
# - rex-project-picker: the cmd+shift+n project picker (actions/project-picker.lua),
#   which lists zoxide folders here or on another Rex host over SSH.
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
    # The task inbox, standalone in a shell (see crates/spawn/src/inbox.rs).
    postInstall = ''
      ln -s rex-spawn $out/bin/rex-inbox
      # The project picker lists this host's folders with zoxide; rex and ssh
      # stay the caller's.
      wrapProgram $out/bin/rex-project-picker --prefix PATH : ${lib.makeBinPath [pkgs.zoxide]}
    '';
    meta.mainProgram = "rex-spawn";
  }
