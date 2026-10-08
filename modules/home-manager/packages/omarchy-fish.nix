{pkgs, ...}: {
  # Shell helpers only; do not import the shared desktop/package suite.
  home.packages = with pkgs; [
    fd
    fswatch
    glow
    iproute2
    macchina
    nix-your-shell
    television
  ];

  programs.lsd = {
    enable = true;
    enableFishIntegration = false;
  };
  programs.zoxide.enable = true;
}
