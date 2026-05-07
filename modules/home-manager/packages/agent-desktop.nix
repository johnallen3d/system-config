{pkgs, ...}: let
  version = "0.1.14";
  release =
    if pkgs.stdenv.hostPlatform.system == "aarch64-darwin"
    then {
      target = "aarch64-apple-darwin";
      hash = "sha256-8b9gCUbZQlRFCv1WhscO7ud51i4Fgo8fLUmSAKSMcKU=";
    }
    else if pkgs.stdenv.hostPlatform.system == "x86_64-darwin"
    then {
      target = "x86_64-apple-darwin";
      hash = "sha256-sb5Oxxdz1Fxkd8t1pIqgmPoGn+igPQoWdDz64/6cnV8=";
    }
    else throw "agent-desktop is only packaged for macOS";
in
  pkgs.stdenvNoCC.mkDerivation {
    pname = "agent-desktop";
    inherit version;

    src = pkgs.fetchurl {
      url = "https://github.com/lahfir/agent-desktop/releases/download/v${version}/agent-desktop-v${version}-${release.target}.tar.gz";
      inherit (release) hash;
    };

    sourceRoot = ".";

    installPhase = ''
      runHook preInstall
      install -Dm755 agent-desktop $out/bin/agent-desktop
      runHook postInstall
    '';

    meta = with pkgs.lib; {
      description = "Native desktop automation CLI for AI agents";
      homepage = "https://github.com/lahfir/agent-desktop";
      license = licenses.asl20;
      platforms = platforms.darwin;
      mainProgram = "agent-desktop";
    };
  }
