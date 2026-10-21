# Credits terminal client; the server itself runs on Omarchy (omarchy-credits.nix).
{
  credits,
  pkgs,
  ...
}: {
  home.packages = [credits.packages.${pkgs.stdenv.hostPlatform.system}.default];

  xdg.configFile."credits/config.toml".text = ''
    url = "https://credits.jallen7usa.com"
  '';
}
