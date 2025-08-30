{
  pkgs,
  brew_bin,
  ...
}: {
  environment = {
    pathsToLink = ["/Applications"];

    systemPath = [
      "${pkgs.path}"
      "/usr/local/bin"
      "$HOME/bin"
      "$HOME/.local/bin"
      "$HOME/.cargo/bin"
      "${brew_bin}"
      "$HOME/.local/share/bob/nvim-bin"
    ];
  };
}
