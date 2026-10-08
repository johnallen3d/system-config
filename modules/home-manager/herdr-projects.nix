{
  config,
  lib,
  pkgs,
  ...
}: let
  favorites = ./dotfiles/config/herdr/plugins/config/herdr.project-picker/projects.toml;
  catalog = builtins.fromTOML (builtins.readFile favorites);
  projects = lib.concatMap (session: session.projects) (builtins.attrValues catalog.sessions);
  manifest = pkgs.writeText "herdr-favorite-projects.json" (builtins.toJSON projects);
  # Omarchy's persistent server uses "default", not the Mac's personal/work
  # sessions. Show the combined catalog there without duplicating declarations.
  pickerCatalog =
    catalog
    // {
      sessions = catalog.sessions // {default.projects = lib.unique projects;};
    };
in {
  home.file.".config/herdr/plugins/config/herdr.project-picker/projects.toml".source =
    (pkgs.formats.toml {}).generate "herdr-picker-projects.toml" pickerCatalog;

  # Clone at activation, never in a Nix build. Authentication and checkouts remain
  # machine-local; existing repositories (including worktrees) are never updated.
  home.activation.herdrFavoriteProjects = lib.hm.dag.entryAfter ["writeBoundary"] ''
    PATH="${lib.makeBinPath [pkgs.git pkgs.openssh]}:$PATH" \
      $DRY_RUN_CMD ${lib.getExe pkgs.python3} ${./scripts/ensure-herdr-projects.py} \
        ${manifest} ${lib.escapeShellArg config.home.homeDirectory}
  '';
}
