# Switchyard's runtime config (~/.config/switchyard/config.toml), read by the
# Rex float tools in ./switchyard (crates/core/src/config.rs). Imported on
# every host that installs switchyard.nix, so catalog and theme edits only
# rewrite this file instead of rebuilding the Rust package.
{
  lib,
  pkgs,
  ...
}: let
  palette = (import ../managed-theme.nix {inherit lib;}).activePalette;
  catalog = builtins.fromTOML (builtins.readFile ../agent-projects/projects.toml);
  projects = profile:
    map (p: {
      inherit profile;
      inherit (p) path clone_url;
      hosts = p.hosts or [];
    })
    (catalog.${profile} or []);
in {
  xdg.configFile."switchyard/config.toml".source = (pkgs.formats.toml {}).generate "switchyard-config.toml" {
    # Rex host labels of the Linux dev machines the spawn picker offers
    # (ctrl+o). The Mac is added at runtime as the config host's own label.
    hosts = ["miller" "drummer" "omarchy"];
    # Hosts "auto" chooses from per group (least busy wins when there are
    # several); a project's `hosts` in projects.toml overrides its group.
    pools = {
      personal = ["omarchy"];
      work = ["miller" "drummer"];
    };
    # Rosé Pine names for the managed theme's colours.
    palette = lib.mapAttrs (_: key: palette.${key}) {
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
    };
    projects = projects "personal" ++ projects "work";
  };
}
