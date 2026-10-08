{pkgs, ...}: {
  # Only opt-in host modules: Omarchy still owns Bash and the desktop.
  imports = [
    ../modules/home-manager/coding-agents.nix
    ../modules/home-manager/omarchy-fish.nix
    ../modules/home-manager/omarchy-herdr.nix
    ../modules/home-manager/omarchy-vnc.nix
  ];

  home = {
    username = "johna";
    homeDirectory = "/home/johna";
    stateVersion = "26.05";
  };

  targets.genericLinux = {
    enable = true;
    # User-level CLI/services must not install or configure GPU drivers.
    gpu.enable = false;
  };

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
