{
  config,
  pkgs,
  ...
}: {
  # Shell helpers only; do not import the shared desktop/package suite.
  home.packages = with pkgs;
    [
      fd
      fswatch
      glow
      iproute2
      macchina
      nix-your-shell
      television
    ]
    ++ [
      (import ./bin/omarchy-fish-default-shell.nix {
        inherit pkgs;
        username = config.home.username;
        homeDir = config.home.homeDirectory;
      })
    ];

  programs.lsd = {
    enable = true;
    enableFishIntegration = false;
  };
  programs.zoxide.enable = true;
}
