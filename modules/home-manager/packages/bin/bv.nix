{pkgs, ...}:
let
  version = "0.11.1";
  arch = if pkgs.stdenv.hostPlatform.isAarch64 then "arm64" else "amd64";
  platform = if pkgs.stdenv.hostPlatform.isDarwin then "darwin" else "linux";
  sha256 = if pkgs.stdenv.hostPlatform.isDarwin && pkgs.stdenv.hostPlatform.isAarch64 then
    "ec53f51b03c70d589fb8bc7de31edf9f3d565f1e044123fe769c1b21696523a3"
  else if pkgs.stdenv.hostPlatform.isDarwin && !pkgs.stdenv.hostPlatform.isAarch64 then
    "478fcbc081464b747faccd6deae765b51758a274015912740fa1665adaeb26e4"
  else if !pkgs.stdenv.hostPlatform.isDarwin && pkgs.stdenv.hostPlatform.isAarch64 then
    "19ba43f084e5c317edc4b22367e94295f7304fe255f78e573718ce1020d60345"
  else
    "cc3b6e733510ed52be1c9b6241f680632075ca4754b410505be5e348c4aaa17f";
in
pkgs.stdenv.mkDerivation {
  pname = "beads-viewer";
  inherit version;

  src = pkgs.fetchurl {
    url = "https://github.com/Dicklesworthstone/beads_viewer/releases/download/v${version}/bv_${version}_${platform}_${arch}.tar.gz";
    inherit sha256;
  };

  sourceRoot = ".";

  installPhase = ''
    mkdir -p $out/bin
    cp bv $out/bin/
  '';

  meta = with pkgs.lib; {
    description = "Terminal User Interface for browsing and managing tasks in projects that use the Beads issue tracking system";
    homepage = "https://github.com/Dicklesworthstone/beads_viewer";
    license = licenses.mit;
    platforms = platforms.unix;
    mainProgram = "bv";
  };
}