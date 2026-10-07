{pkgs, ...}: {
  # Deliberately no shared imports: Omarchy owns the shell and desktop.
  home = {
    username = "johna";
    homeDirectory = "/home/johna";
    stateVersion = "26.05";
  };

  targets.genericLinux = {
    enable = true;
    # This CLI-only POC must not install or configure GPU drivers.
    gpu.enable = false;
  };

  # Do not generate user services or session environment for the desktop.
  systemd.user.enable = false;

  # Keep the proof small and avoid desktop MIME database integration.
  xdg.mime.enable = false;
  manual.manpages.enable = false;

  programs = {
    home-manager.enable = true;
    jq.enable = true;
    man.enable = false;
  };

  xdg.configFile."nix-home-manager-poc/status.json".text =
    builtins.toJSON {
      host = "omarchy";
      managedBy = "home-manager";
      package = "jq";
      packageVersion = pkgs.jq.version;
      scope = "isolated-cli-poc";
    }
    + "\n";
}
