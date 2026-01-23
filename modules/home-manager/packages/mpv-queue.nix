{pkgs, ...}:
pkgs.rustPlatform.buildRustPackage {
  pname = "mpv-queue";
  version = "0.1.0";

  src = /Users/john.allen/dev/src/playground/mpv-queue;

  cargoLock = {
    lockFile = /Users/john.allen/dev/src/playground/mpv-queue/Cargo.lock;
  };

  meta = with pkgs.lib; {
    description = "Minimal TUI for browsing and controlling the mpv playlist queue";
    license = licenses.mit;
    mainProgram = "mpv-queue";
  };
}
