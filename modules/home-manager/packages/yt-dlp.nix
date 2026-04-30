{pkgs}: let
  pinnedPkgs = import (builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/0726a0ecb6d4e08f6adced58726b95db924cef57.tar.gz";
    sha256 = "sha256-EHq1/OX139R1RvBzOJ0aMRT3xnWyqtHBRUBuO1gFzjI=";
  }) {
    inherit (pkgs.stdenv.hostPlatform) system;
    config.allowUnfree = true;
  };
in
  # nixpkgs wires yt-dlp to ffmpeg-headless, but that binary is being SIGKILLed
  # on this macOS setup. Reuse current pkgs.ffmpeg for yt-dlp postprocessing.
  pinnedPkgs.yt-dlp.override {ffmpeg-headless = pkgs.ffmpeg;}
