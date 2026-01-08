{
  pkgs,
  brew_bin,
  ...
}: let
  scripts = [
    (import ./bin/connect-air-pods.nix {
      inherit pkgs;
      inherit brew_bin;
    })
    (import ./bin/toggle-air-pods.nix {
      inherit pkgs;
      inherit brew_bin;
    })
  ];
in {
  home.packages = with pkgs;
    [
      mas
      sketchybar
      (python3.withPackages (ps: [ps.pyobjc-framework-Quartz]))
    ]
    ++ scripts;
}
