{
  pkgs,
  brew_bin,
  ...
}: {
  pathsToLink = ["/Applications"];

  systemPath = [
    "${pkgs.path}"
    "/usr/local/bin"
    "$HOME/bin"
    "$HOME/.local/bin"
    "$HOME/.cargo/bin"
    "${brew_bin}"
  ];
}
