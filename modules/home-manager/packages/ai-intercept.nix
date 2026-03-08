{pkgs, ...}:
let
  srcPath = /Users/john.allen/dev/src/playground/ai-intercept;
in
pkgs.rustPlatform.buildRustPackage {
  pname = "ai-intercept";
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
    lockFile = /Users/john.allen/dev/src/playground/ai-intercept/Cargo.lock;
  };

  meta = with pkgs.lib; {
    description = "Shared policy guard for AI coding tools (Claude Code, OpenCode, etc.)";
    license = licenses.mit;
    mainProgram = "ai-intercept";
  };
}
