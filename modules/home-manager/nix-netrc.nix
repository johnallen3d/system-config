# Point user-level Nix at a host-local netrc for authenticated flake inputs
# (Rex's pre-release flake). The netrc holds tokens, so it stays unmanaged:
#   machine pkgs.superlogical.com login rex password <REX_PACKAGE_TOKEN>
{config, ...}: {
  xdg.configFile."nix/nix.conf".text = ''
    netrc-file = ${config.xdg.configHome}/nix/netrc
  '';
}
