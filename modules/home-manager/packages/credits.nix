{
  pkgs,
  src,
  ...
}: let
  manifest = builtins.fromTOML (builtins.readFile "${src}/Cargo.toml");
  caBundle = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
in
  pkgs.rustPlatform.buildRustPackage {
    pname = "credits";
    version = manifest.package.version;

    inherit src;

    # Read dependency hashes from upstream so input updates need no manual hash edits.
    cargoLock.lockFile = "${src}/Cargo.lock";

    nativeBuildInputs = [pkgs.makeBinaryWrapper];
    SSL_CERT_FILE = caBundle;
    postFixup = ''
      wrapProgram "$out/bin/credits" --set-default SSL_CERT_FILE ${caBundle}
    '';

    meta = with pkgs.lib; {
      description = "Movie and TV browser";
      license = licenses.mit;
      mainProgram = "credits";
    };
  }
