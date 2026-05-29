# Consolidated pi agent extensions and themes.
#
# Code extensions (JS/TS) → ~/.pi/agent/extensions/<name>/
# Theme-only packages or local JSON files → ~/.pi/agent/themes/<theme-name>.json
#
# Local extension code lives under ./pi/extensions/<name>/index.ts.
# To add a new extension or theme:
#   1. Add entry to ./pi/local-extensions.nix, ./pi/packaged-extensions.nix, or ./pi/themes.nix
#   2. Add package-lock.json beside the relevant package metadata when packaging is needed
#   3. Use a dummy npmDepsHash, run `mise run nix-rebuild -- --switch-only`, grab real hash from error
#
{pkgs, ...}: let
  lib = pkgs.lib;
  localExtensions = import ./pi/local-extensions.nix {inherit lib;};
  localPersonalExtensions = import ./pi/local-personal-extensions.nix {inherit lib;};
  localWorkExtensions = import ./pi/local-work-extensions.nix {};
  extensions = import ./pi/packaged-extensions.nix {};
  themes = import ./pi/themes.nix {};
  themeSource = theme:
    if theme ? source
    then theme.source
    else "${theme.pkg}/themes/${theme.file}";
in {
  home.file =
    # Shared extensions — personal context
    (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi/extensions/${name}" {source = pkg;})
      (extensions // localExtensions // localPersonalExtensions))
    # Shared extensions — also present in work context
    // (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi-work/extensions/${name}" {source = pkg;})
      (extensions // localExtensions))
    # Work-only extensions
    // (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi-work/extensions/${name}" {source = pkg;})
      localWorkExtensions)
    # Themes — personal context (pi-work symlinks to this dir, see pi-settings.nix)
    // (lib.mapAttrs'
      (name: theme:
        lib.nameValuePair ".config/pi/themes/${name}.json" {source = themeSource theme;})
      themes);
}
