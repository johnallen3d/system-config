{pkgs, ...}: {
  home.packages = with pkgs; [
    gcc
    trashy
    xclip
  ];

  # programs.chromium = {
  #   enable = true;
  # };
}
