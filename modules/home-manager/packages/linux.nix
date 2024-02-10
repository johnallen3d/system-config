{pkgs, ...}: {
  home.packages = with pkgs; [
    trashy
    xclip
  ];

  programs.chromium = {
    enable = true;
  };
}
