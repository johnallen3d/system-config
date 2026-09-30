{
  pkgs,
  src,
  ...
}: let
  manifest = builtins.fromTOML (builtins.readFile "${src}/Cargo.toml");
in
  pkgs.rustPlatform.buildRustPackage {
    pname = "yem";
    version = manifest.package.version;

    inherit src;

    cargoLock = {
      lockFile = "${src}/Cargo.lock";
    };

    nativeBuildInputs = [
      pkgs.cmake
    ];

    meta = with pkgs.lib; {
      description = "Minimal TUI for browsing and controlling the mpv playlist queue";
      license = licenses.mit;
      mainProgram = "yem";
    };
  }
