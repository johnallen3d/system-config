{pkgs, ...}: {
  fonts = {
    # paid fonts (eg. Font Awesome Pro) installed at "modules/home-manager/default.nix"
    fontDir.enable = true;

    packages = with pkgs; [
      cascadia-code
      monaspace
      (nerdfonts.override {fonts = ["CascadiaCode" "Hack"];})
    ];
  };
}
