{
  lib,
  pkgs,
  ...
}: let
  managedTheme = import ../managed-theme.nix {inherit lib;};
  jsonFormat = pkgs.formats.json {};
in
  lib.mapAttrs' (variant: theme:
    lib.nameValuePair (managedTheme.themeName variant) {
      source = jsonFormat.generate "${managedTheme.themeName variant}.json" theme;
    }) managedTheme.piThemes
