# Credits terminal client (and the macOS launcher on Darwin); the server
# itself runs on Omarchy (omarchy-credits.nix).
{
  credits,
  lib,
  pkgs,
  ...
}: let
  inherit (pkgs.stdenv.hostPlatform) isDarwin system;
  launcher = credits.packages.${system}.launcher;
in {
  home.packages = [credits.packages.${system}.default] ++ lib.optional isDarwin launcher;

  xdg.configFile."credits/config.toml".text = ''
    url = "https://credits.jallen7usa.com"
  '';

  # Option-Space launcher, started at login; quitting it from the menu
  # keeps it stopped until the next login, a crash restarts it.
  launchd.agents.credits-launcher = lib.mkIf isDarwin {
    enable = true;
    config = {
      Label = "org.nix-community.home.credits-launcher";
      ProgramArguments = ["${launcher}/Applications/Credits Launcher.app/Contents/MacOS/CreditsLauncher"];
      RunAtLoad = true;
      KeepAlive.SuccessfulExit = false;
      ProcessType = "Interactive";
    };
  };
}
