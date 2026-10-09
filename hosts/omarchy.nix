{
  config,
  lib,
  lop,
  pkgs,
  ...
}: let
  homeDir = config.home.homeDirectory;
  lopPackage = lop.packages.${pkgs.stdenv.hostPlatform.system}.default.overrideAttrs (old: {
    # Herdr's executable fixtures intermittently fail when tested concurrently on Linux.
    cargoTestFlags = (old.cargoTestFlags or []) ++ ["-- --test-threads=1"];
    # The launchctl test fixture assumes /bin/cat, absent in Linux Nix sandboxes.
    postPatch =
      (old.postPatch or "")
      + ''
        substituteInPlace src/schedule.rs \
          --replace-fail '/bin/cat' '${pkgs.coreutils}/bin/cat'
      '';
  });
  lopPath =
    lib.makeBinPath [pkgs.coreutils pkgs.git pkgs.herdr pkgs.openssh pkgs.worktrunk]
    + ":${homeDir}/.local/bin:${homeDir}/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin";
in {
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
    packages = [lopPackage];
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

  # Match the Mac's Nix-owned policy; exclusions stay writable and host-local.
  xdg.configFile."lop/config.toml".source = ../modules/home-manager/dotfiles/config/lop/config.toml;
  xdg.configFile."lop/schedule.toml".text = ''
    # Managed by Home Manager; Linux scheduling uses lop.timer, not lop schedule.
    mode = "prune"
    interval_seconds = 60
  '';

  # Lop's native schedule backend is macOS-only. Mirror its prune --yes command
  # and one-minute cadence with a user timer, without overlapping service runs.
  systemd.user.services.lop = {
    Unit.Description = "Conservative cleanup of stale Git worktrees";
    Service = {
      Type = "oneshot";
      ExecStart = "${lib.getExe lopPackage} prune --yes";
      WorkingDirectory = homeDir;
      Environment = [
        "HOME=${homeDir}"
        "PATH=${lopPath}"
        "GIT_TERMINAL_PROMPT=0"
        ''"GIT_SSH_COMMAND=${pkgs.openssh}/bin/ssh -o BatchMode=yes"''
      ];
      UMask = "0077";
    };
  };
  systemd.user.timers.lop = {
    Unit.Description = "Run Lop pruning every minute";
    Timer = {
      OnActiveSec = "1s";
      OnUnitActiveSec = "60s";
      AccuracySec = "1s";
      Unit = "lop.service";
    };
    Install.WantedBy = ["timers.target"];
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
