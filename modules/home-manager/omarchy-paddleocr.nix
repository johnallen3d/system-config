{pkgs, ...}: {
  # Required model-download SDK; retain the existing Claude unfree predicate.
  nixpkgs.config.allowUnfreePackages = ["aistudio-sdk"];

  home.packages = [(import ./packages/omarchy-paddleocr.nix {inherit pkgs;})];
}
