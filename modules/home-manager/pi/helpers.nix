{pkgs, ...}: {
  mkPiExtension = {
    pname,
    version,
    url ? "https://registry.npmjs.org/${pname}/-/${pkgs.lib.lists.last (pkgs.lib.splitString "/" pname)}-${version}.tgz",
    hash,
    npmDepsHash,
    lockfile,
    description ? "",
    homepage ? "",
    forceEmptyCache ? false,
    npmInstallFlags ? [],
    extraInstallPhase ? "",
    extraPostPatch ? "",
    nativeBuildInputs ? [],
  }:
    pkgs.buildNpmPackage {
      inherit pname version npmDepsHash forceEmptyCache npmInstallFlags nativeBuildInputs;

      src = pkgs.fetchurl {inherit url hash;};

      sourceRoot = "package";
      dontNpmBuild = true;

      postPatch = ''
        cp ${lockfile} package-lock.json
        ${extraPostPatch}
      '';

      installPhase = ''
        runHook preInstall
        mkdir -p $out
        cp -r ./* $out/
        ${extraInstallPhase}
        runHook postInstall
      '';

      meta = with pkgs.lib; {
        inherit description homepage;
        license = licenses.mit;
      };
    };
}
