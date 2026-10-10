{pkgs, ...}: let
  # This is Amfaro's Python SQL tool, not haskellPackages.jarify. Keep its
  # dependencies isolated in uv's cache, matching the Mac's installed version.
  jarify = pkgs.writeShellScriptBin "jarify" ''
    exec ${pkgs.uv}/bin/uv tool run --from jarify==0.14.0 jarify "$@"
  '';
in {
  home.packages = with pkgs; [
    alejandra
    basedpyright
    biome
    curl
    duckdb
    fd
    gcc
    harper
    jarify
    kcl
    kcl-language-server
    lua-language-server
    markdownlint-cli2
    marksman
    nixd
    postgresql
    prettier
    ripgrep
    ruff
    rust-analyzer
    rustfmt
    sqlite
    stylua
    tree-sitter
    vscode-langservers-extracted
    wl-clipboard
    yamlfmt
  ];
}
