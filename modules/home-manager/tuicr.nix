{
  lib,
  pkgs,
  ...
}: let
  managedTheme = import ./managed-theme.nix {inherit lib;};
  c = managedTheme.activeTheme.palette;
  tuicr = pkgs.tuicr.overrideAttrs (old:
    lib.optionalAttrs pkgs.stdenv.hostPlatform.isDarwin {
      # The Rust setup hook requires system libraries instead of vendored copies.
      nativeBuildInputs = (old.nativeBuildInputs or []) ++ [pkgs.pkg-config];
      buildInputs = (old.buildInputs or []) ++ [pkgs.libgit2 pkgs.oniguruma pkgs.zlib];
    });
in {
  home.packages = [tuicr];

  xdg.configFile =
    {
      "tuicr/config.toml".source = (pkgs.formats.toml {}).generate "tuicr-config.toml" {
        theme = managedTheme.activeTheme.hyphenName;
        username = "johnallen3d";
        mouse = false;
        no_update_check = true;
        diff_watch_interval_ms = 1000;
        comment_vim = true;
        diff_view = "side-by-side";
        show_reviewed = false;
        comment_types = [
          {
            id = "issue";
            definition = "must fix before merge";
            color = c.red;
          }
          {
            id = "suggestion";
            definition = "optional improvement";
            color = c.blue;
          }
          {
            id = "question";
            definition = "needs clarification; don't change code yet";
            color = c.yellow;
          }
          {
            id = "nit";
            definition = "trivial, fix if convenient";
            color = c.muted;
          }
        ];
      };
    }
    # Local themes for every managed variant; syntax_theme points at the tmTheme beside each.
    // lib.concatMapAttrs (variant: _: let
      name = managedTheme.hyphenThemeName variant;
    in {
      "tuicr/themes/${name}.toml".text = managedTheme.tuicrThemes.${variant};
      "tuicr/themes/${name}.tmTheme".text = managedTheme.batThemes.${variant};
    })
    managedTheme.palettes;
}
