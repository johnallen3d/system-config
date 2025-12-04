{pkgs, ...}:
pkgs.rustPlatform.buildRustPackage rec {
  pname = "nail-parquet";
  version = "1.6.6";

  src = pkgs.fetchCrate {
    inherit pname version;
    hash = "sha256-qC+4GVRVc99EFCT8yI0Qb+SLdjJ1PzvyLOrj4kYh0Hg=";
  };

  cargoHash = "sha256-aHVcVmRT1XfRBk4mXOXaEJ+VfydBJ9cEnCddFoR//6o=";

  # Tests require network access
  doCheck = false;

  meta = with pkgs.lib; {
    description = "Fast CLI tool for viewing, querying, and converting Parquet files";
    homepage = "https://github.com/Vitruves/nail-parquet";
    license = licenses.mit;
    mainProgram = "nail";
  };
}
