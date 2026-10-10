{lib, ...}: {
  # Reuse the Mac editor only; do not import its desktop or package suite.
  imports = [
    ./nvim
    ./packages/omarchy-nvim.nix
  ];

  # The shared Mac module leaves the binary to Bob. Omarchy uses locked Nix.
  programs.neovim.enable = lib.mkForce true;

  home.sessionVariables = {
    EDITOR = lib.mkForce "nvim-editor";
    VISUAL = lib.mkForce "nvim-editor";
  };

  xdg.configFile."markdownlint/.markdownlint-cli2.jsonc".source =
    ./dotfiles/config/markdownlint/.markdownlint-cli2.jsonc;
}
