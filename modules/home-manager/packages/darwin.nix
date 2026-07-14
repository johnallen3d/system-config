{
  pkgs,
  brew_bin,
  ...
}: let
  agent-desktop = import ./agent-desktop.nix {inherit pkgs;};
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
      agent-desktop
      macchina
      mas
      (python3.withPackages (ps: [ps.pyobjc-framework-Quartz]))
    ]
    ++ scripts;
}
