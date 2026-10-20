{pkgs, ...}: let
  # Keep one current coordinator available even inside older task worktrees.
  # Only these tools are packaged; never include a checkout, profile, or secret.
  tooling = pkgs.runCommand "system-config-deployment-tools" {} ''
    mkdir -p $out/.mise/{scripts,tasks}
    cp ${../../.mise/scripts/deployment_state.py} $out/.mise/scripts/deployment_state.py
    cp ${../../.mise/scripts/update-system-omarchy} $out/.mise/scripts/update-system-omarchy
    cp ${../../.mise/tasks/update-system} $out/.mise/tasks/update-system
    cp ${../../.mise/tasks/nix-rebuild} $out/.mise/tasks/nix-rebuild
  '';
in {
  home.packages = [
    (pkgs.writeShellApplication {
      name = "system-config-deploy";
      runtimeInputs = [pkgs.python3 pkgs.git pkgs.openssh];
      text = ''
        exec python3 ${tooling}/.mise/scripts/deployment_state.py apply "$@"
      '';
    })
  ];
  home.file.".local/share/system-config-deploy".source = tooling;
}
