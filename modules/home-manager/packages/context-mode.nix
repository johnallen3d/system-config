{pkgs, ...}:
pkgs.buildNpmPackage rec {
  pname = "context-mode";
  version = "1.0.22";

  src = pkgs.fetchurl {
    url = "https://registry.npmjs.org/${pname}/-/${pname}-${version}.tgz";
    hash = "sha256-BJtiwRZCGFwEZ6J50+erOu6n3Fkr5vF0k7B64GScSZ8=";
  };

  sourceRoot = ".";

  npmDepsHash = "sha256-xQjKg1TcHiK0J0oeqjC/1Qq91tJqGw+ZaBZ9Hxn3nj0=";

  postUnpack = ''
    cp ${pkgs.fetchurl {
      url = "https://raw.githubusercontent.com/mksglu/context-mode/main/package-lock.json";
      hash = "sha256-9VFpPIgc2S2MYxEsqrNH67VWNonGg3UPHUHhLF9UG7k=";
    }} package-lock.json
  '';

  nativeBuildInputs = with pkgs; [
    python3
    pkg-config
  ];

  buildInputs = with pkgs; [
    sqlite
  ];

  dontNpmBuild = true;

  meta = with pkgs.lib; {
    description = "MCP plugin that saves context window by sandboxing code execution with FTS5 knowledge base";
    homepage = "https://github.com/mksglu/context-mode";
    license = licenses.elastic20;
    mainProgram = "context-mode";
  };
}
