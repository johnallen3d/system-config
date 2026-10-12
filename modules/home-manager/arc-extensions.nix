{
  lib,
  pkgs,
  ...
}: let
  imdbEnhanced = import ./packages/imdb-enhanced-extension.nix {inherit pkgs;};
in {
  # Opted in by m4-mbp only. Arc remains installed by the Darwin Homebrew module.
  # Manage immutable extension files, never Arc profiles or chrome.storage.local.
  home.file.".local/share/browser-extensions/imdb-enhanced" = lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
    source = "${imdbEnhanced}/share/imdb-enhanced";
  };
}
