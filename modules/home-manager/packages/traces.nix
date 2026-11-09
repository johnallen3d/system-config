{pkgs}: let
  inherit (pkgs) lib;
  version = "0.6.45";
  releases = {
    aarch64-darwin = {
      binary = "traces-darwin-arm64";
      sha256 = "3cdaafcc3d112c06ac14db49959ebecbf0e95ec5c149746e71c21899cc1362b4";
    };
    x86_64-darwin = {
      binary = "traces-darwin-x64";
      sha256 = "7efb9bbbb2d7c7412b43f8a3f8b5a89b2896c2e2f100a339d1b5b2daccb42ad7";
    };
    aarch64-linux = {
      binary = "traces-linux-arm64";
      sha256 = "cd1d6754bce4b199fd0ec70c3c35e5bfb58e826acf7cc235a61bcfbdcb8b29db";
    };
    x86_64-linux = {
      # The baseline Bun runtime also supports the 2013 Mac Pro CPUs.
      binary = "traces-linux-x64-baseline";
      sha256 = "423ba0441311766f3400a02c18fb7c0ef33aa81d8a643214f7a3656a10b6e5af";
    };
  };
  release = releases.${pkgs.stdenv.hostPlatform.system};
in
  pkgs.stdenvNoCC.mkDerivation {
    pname = "traces";
    inherit version;

    src = pkgs.fetchurl {
      url = "https://github.com/market-dot-dev/traces-binaries/releases/download/v${version}/${release.binary}";
      inherit (release) sha256;
    };

    dontUnpack = true;
    dontBuild = true;
    # Stripping a compiled Bun executable removes its embedded application.
    dontStrip = true;
    nativeBuildInputs = lib.optionals pkgs.stdenv.hostPlatform.isLinux [pkgs.autoPatchelfHook];
    buildInputs = lib.optionals pkgs.stdenv.hostPlatform.isLinux [pkgs.stdenv.cc.cc.lib];

    installPhase = ''
      runHook preInstall
      install -Dm755 "$src" "$out/bin/traces"
      runHook postInstall
    '';

    meta = {
      description = "Browse, search, and share AI coding-agent sessions";
      homepage = "https://traces.com/";
      license = lib.licenses.unfree;
      platforms = builtins.attrNames releases;
      mainProgram = "traces";
    };
  }
