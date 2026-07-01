# Consolidated pi agent extensions, skills, and themes.
#
# Managed code extensions (JS/TS) → ~/.config/pi{,-work}/extensions/<name>/
# Managed skills                → ~/.config/pi{,-work}/skills/<name>/
# Theme-only packages/local JSON → ~/.config/pi/themes/<theme-name>.json
#
# Local extension code lives under ./pi/extensions/<name>/index.ts.
# Legacy harness installers that still hardcode ~/.pi/agent/{extensions,skills}
# can be bridged into both managed Pi profiles with out-of-store symlinks here.
#
# To add a new managed extension or theme:
#   1. Add entry to ./pi/local-extensions.nix, ./pi/packaged-extensions.nix, or ./pi/themes.nix
#   2. Add package-lock.json beside the relevant package metadata when packaging is needed
#   3. Use a dummy npmDepsHash, run `mise run nix-rebuild -- --switch-only`, grab real hash from error
#
{
  config,
  pkgs,
  ...
}: let
  lib = pkgs.lib;
  mkOutOfStoreSymlink = config.lib.file.mkOutOfStoreSymlink;
  homeDir = config.home.homeDirectory;
  localExtensions = import ./pi/local-extensions.nix {inherit lib;};
  localPersonalExtensions = import ./pi/local-personal-extensions.nix {inherit lib;};
  localWorkExtensions = import ./pi/local-work-extensions.nix {};
  extensions = import ./pi/packaged-extensions.nix {};
  legacyHarnessExtensions = {
    supacode = mkOutOfStoreSymlink "${homeDir}/.pi/agent/extensions/supacode";
  };
  legacyHarnessSkills = {
    supacode-cli = mkOutOfStoreSymlink "${homeDir}/.pi/agent/skills/supacode-cli";
  };
  themes = import ./pi/themes.nix {inherit lib pkgs;};
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
    # Harness-installed legacy integrations — exposed in both managed profiles.
    // (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi/extensions/${name}" {source = pkg;})
      legacyHarnessExtensions)
    // (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi-work/extensions/${name}" {source = pkg;})
      legacyHarnessExtensions)
    // (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi/skills/${name}" {source = pkg;})
      legacyHarnessSkills)
    // (lib.mapAttrs'
      (name: pkg:
        lib.nameValuePair ".config/pi-work/skills/${name}" {source = pkg;})
      legacyHarnessSkills)
    # Themes — personal context (pi-work symlinks to this dir, see pi-settings.nix)
    // (lib.mapAttrs'
      (name: theme:
        lib.nameValuePair ".config/pi/themes/${name}.json" {source = themeSource theme;})
      themes);
}
