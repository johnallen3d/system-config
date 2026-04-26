{pkgs, ...}:
let
  srcPath = /Users/john.allen/dev/src/playground/yem;
in
pkgs.rustPlatform.buildRustPackage {
  pname = "yem";
  version = "0.1.0";

  src = pkgs.lib.cleanSourceWith {
    src = srcPath;
    filter = path: type:
      let
        baseName = baseNameOf path;
      in
      # Exclude .beads directory and other non-source files
      !(baseName == ".beads" || baseName == ".git" || baseName == "target");
  };

  cargoLock = {
    lockFile = /Users/john.allen/dev/src/playground/yem/Cargo.lock;
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
