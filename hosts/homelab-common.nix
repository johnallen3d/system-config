# Shared by pi-cielo homelab hosts (Debian; services stay in pi-cielo's Docker
# Compose). Deliberately slim: a first step toward Nix-managing the homelab,
# not an Omarchy profile. Deployed separately (`mise run homelab-deploy`), never
# by update-system.
{
  host,
  rex,
  user,
  ...
}: {
  imports = [rex.homeManagerModules.default];

  # Personal Rex server as a user service (lingering keeps it up). Debian owns
  # ~/.ssh/config here, so don't install the ssh guard.
  programs.rex.sshGuard = false;
  services.rex = {
    enable = true;
    # Rex's own tailnet node (owner-only); the Mac app connects to it remotely.
    tailscale = {
      enable = true;
      hostname = "rex-${host}";
    };
  };

  home = {
    username = user;
    homeDirectory = "/home/${user}";
    stateVersion = "26.05";
  };

  targets.genericLinux = {
    enable = true;
    gpu.enable = false;
  };

  xdg.mime.enable = false;
  manual.manpages.enable = false;

  programs = {
    home-manager.enable = true;
    man.enable = false;
  };
}
