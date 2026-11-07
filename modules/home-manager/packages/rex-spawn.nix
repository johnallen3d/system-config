# The ctrl+cmd+n spawn picker for Rex (see ../dotfiles/config/rex/actions/spawn.lua):
# start agent work in a new worktree of a catalog project on a chosen dev host.
# Like rex-tab-picker it runs in a float on the focused session's host, and its
# --run mode runs in the new tab on the target host, so it is installed on
# every host. The project catalog and dev host list are compiled in.
{
  pkgs,
  palette,
}: let
  inherit (pkgs) lib;
  catalog = builtins.fromTOML (builtins.readFile ../agent-projects/projects.toml);
  rows = profile:
    map (p: "${profile}\t${p.path}\t${p.clone_url}\t${lib.concatStringsSep " " (p.hosts or [])}")
    (catalog.${profile} or []);
in
  pkgs.rustPlatform.buildRustPackage {
    pname = "rex-spawn";
    version = "0.1.0";
    src = lib.cleanSourceWith {
      src = ./rex-spawn;
      filter = path: _: baseNameOf path != "target";
    };
    cargoLock.lockFile = ./rex-spawn/Cargo.lock;
    env = {
      RSP_PROJECTS = lib.concatStringsSep "\n" (rows "personal" ++ rows "work");
      # Rex host labels of the Linux dev machines the picker offers (ctrl+o).
      # The Mac is added at runtime as the config host's own label.
      RSP_HOSTS = "miller drummer omarchy";
      # Hosts "auto" chooses from per group (least busy wins when there are
      # several); a project's `hosts` in projects.toml overrides its group.
      RSP_POOLS = "personal=omarchy work=miller,drummer";
      # Rosé Pine names for the managed theme's colours, as in rex-tab-picker.
      RTP_PALETTE = lib.concatStringsSep ";" (lib.mapAttrsToList (name: key: "${name}=${palette.${key}}") {
        base = "bg";
        surface = "bgDark";
        overlay = "bgHighlight";
        hl_med = "bgVisual";
        hl_high = "gutter";
        text = "text";
        subtle = "muted";
        muted = "comment";
        love = "red";
        gold = "yellow";
        rose = "orange";
        pine = "green";
        foam = "cyan";
        iris = "purple";
      });
    };
    meta.mainProgram = "rex-spawn";
  }
