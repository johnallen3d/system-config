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

  # Only Omarchy needs this SSH fallback; share it across both editor profiles.
  xdg.configFile."nvim/plugin/clipboard.lua".source = ./omarchy-nvim/clipboard.lua;
  xdg.configFile."nvim-editor/plugin/clipboard.lua".source = ./omarchy-nvim/clipboard.lua;

  xdg.configFile."markdownlint/.markdownlint-cli2.jsonc".source =
    ./dotfiles/config/markdownlint/.markdownlint-cli2.jsonc;
}
