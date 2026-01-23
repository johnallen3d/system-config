{pkgs, ...}:
let
  srcPath = /Users/john.allen/dev/src/playground/mpv-queue;
in
pkgs.rustPlatform.buildRustPackage {
  pname = "mpv-queue";
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
    lockFile = /Users/john.allen/dev/src/playground/mpv-queue/Cargo.lock;
  };

  meta = with pkgs.lib; {
    description = "Minimal TUI for browsing and controlling the mpv playlist queue";
    license = licenses.mit;
    mainProgram = "mpv-queue";
  };
}
