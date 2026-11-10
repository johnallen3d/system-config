# Switchyard, the Rex float tools (flake input `switchyard`,
# ~/dev/src/playground/switchyard). Its Home Manager module installs the
# binaries, writes ~/.config/switchyard/config.toml from these settings and,
# on the Mac, links the Rex Lua to ~/.config/rex/switchyard. Imported on every
# host: the floats and `rex-spawn --run` run on whichever host the focused
# session lives on. Settings edits only rewrite the config file.
{
  lib,
  pkgs,
  switchyard,
  ...
}: let
  palette = (import ../managed-theme.nix {inherit lib;}).activePalette;
  catalog = builtins.fromTOML (builtins.readFile ../agent-projects/projects.toml);
  githubTracker = url: let
    m = builtins.match "https://github.com/([^/]+/[^/]+)\\.git" url;
  in
    if m == null
    then throw "switchyard-config: no tracker for ${url}"
    else "github:${builtins.head m}";
  projects = profile:
    map (p: {
      inherit profile;
      inherit (p) path clone_url;
      hosts = p.hosts or [];
      # Personal projects set their Fizzy board; work projects use GitHub.
      tracker = p.tracker or (githubTracker p.clone_url);
    })
    (catalog.${profile} or []);
in {
  imports = [switchyard.homeManagerModules.default];

  programs.switchyard = {
    enable = true;
    package = switchyard.packages.${pkgs.stdenv.hostPlatform.system}.default;
    settings = {
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
  };
}
