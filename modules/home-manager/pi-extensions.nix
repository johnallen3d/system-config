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
  # The Mac usage footer falls back across profile auth files. Do not enable
  # that cross-profile credential read on standalone Linux agent hosts.
  localPersonalExtensions =
    lib.filterAttrs
    (name: _: config.codingAgents.enableCrossProfileUsageFooter || name != "usage-footer")
    (import ./pi/local-personal-extensions.nix {inherit lib;});
  localWorkExtensions = import ./pi/local-work-extensions.nix {};
  extensions = import ./pi/packaged-extensions.nix {};
  legacyHarnessExtensions = lib.optionalAttrs config.codingAgents.enableLegacyHarnessBridges {
    supacode = mkOutOfStoreSymlink "${homeDir}/.pi/agent/extensions/supacode";
  };
  themes = import ./pi/themes.nix {inherit lib pkgs;};
  themeSource = theme:
    if theme ? source
    then theme.source
    else "${theme.pkg}/themes/${theme.file}";
in {
  options.codingAgents = {
    enableCrossProfileUsageFooter = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable the personal usage footer that falls back across Pi profile credentials.";
    };
    enableLegacyHarnessBridges = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Link externally installed legacy harness extensions into managed Pi profiles.";
    };
  };

  config.home.file =
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
    # Themes — personal context (pi-work symlinks to this dir, see pi-settings.nix)
    // (lib.mapAttrs'
      (name: theme:
        lib.nameValuePair ".config/pi/themes/${name}.json" {source = themeSource theme;})
      themes);
}
