{
  config,
  host,
  lib,
  lop,
  pkgs,
  rex,
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
  # Mac (deploys) plus each Linux host's own key, for cross-host rsync/scp.
  # Omarchy uses OpenSSH; Miller and Drummer use Tailscale SSH (tailnet policy).
  authorizedKeys = pkgs.writeText "authorized_keys" ''
    ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINGs0qwPKIoejl6w0R0UKGM4i3WoyJI9WooAkEvSQKq6 mac
    ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINZEUGBGQyM7PFS1GPkW+4sUcOK+graXttptqcNRRH2a omarchy
    ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIItN4G6hV5/dv26t6WGKd7rrpa0HTgsLF5zqGp2i+2Dm miller
    ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIC32sawjNZMspwhMgXwCqL1Btq5JDqjdJvZD6eFQsfq1 drummer
  '';
  lopPath =
    lib.makeBinPath [pkgs.coreutils pkgs.git pkgs.openssh pkgs.worktrunk]
    + ":${homeDir}/.local/bin:${homeDir}/.nix-profile/bin:/usr/local/bin:/usr/bin:/bin";
in {
  # Shared by every Omarchy (Arch) host. Host files add their singletons.
  # Only opt-in host modules: Omarchy still owns Bash and the desktop.
  imports = [
    ../modules/home-manager/coding-agents.nix
    ../modules/home-manager/git
    ../modules/home-manager/omarchy-beszel.nix
    ../modules/home-manager/omarchy-fish.nix
    ../modules/home-manager/omarchy-nvim.nix
    ../modules/home-manager/omarchy-paddleocr.nix
    ../modules/home-manager/omarchy-vnc.nix
    # The Mac's cmd+k tab, cmd+shift+n project and ctrl+cmd+n spawn pickers
    # open their floats here when an Omarchy session is focused; spawned work
    # also runs here through switchyard, which needs wt.
    ../modules/home-manager/packages/switchyard-config.nix
    ../modules/home-manager/nix-netrc.nix
    rex.homeManagerModules.default
  ];

  # Personal Rex server as a user service (lingering keeps it up). Omarchy owns
  # ~/.ssh/config, so `rex terminfo setup` installs the ssh guard there instead.
  programs.rex.sshGuard = false;
  services.rex = {
    enable = true;
    # Rex's own tailnet node (owner-only); the Mac app connects to it remotely.
    # Each host file sets its unique tailscale.hostname.
    tailscale.enable = true;
  };

  # Clients of Omarchy's central gateway; only omarchy.nix runs the server.
  subscriptionProxy.enable = true;

  # Host-local daemon; keep pairing and folder choices writable in Syncthing.
  services.syncthing = {
    enable = true;
    guiAddress = "127.0.0.1:8384";
    overrideDevices = false;
    overrideFolders = false;
    # Tailscale Serve (and Omarchy's pi-01-only LAN forwarder) use this loopback GUI.
    settings.gui.insecureSkipHostcheck = true;
  };

  home = {
    username = "johna";
    homeDirectory = "/home/johna";
    stateVersion = "26.05";
    packages = [lopPackage pkgs.worktrunk];
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

  # Shared Git policy; sign with each host's own key (registered on GitHub).
  # Omarchy's gh stays mise-managed; Nix gh only serves HTTPS credentials.
  programs.git = {
    signing.key = "${homeDir}/.ssh/id_ed25519";
    settings.credential = let
      helper = ["" "!${lib.getExe pkgs.gh} auth git-credential"];
    in {
      "https://github.com" = {inherit helper;};
      "https://gist.github.com" = {inherit helper;};
    };
  };

  # A real file, not a store symlink: sshd StrictModes rejects group-writable
  # /nix/store. Replaced on every activation; add keys here, not by hand.
  home.activation.sshAuthorizedKeys = lib.hm.dag.entryAfter ["writeBoundary"] ''
    run install -d -m 700 ${homeDir}/.ssh
    run install -m 600 ${authorizedKeys} ${homeDir}/.ssh/authorized_keys
  '';

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
      inherit host;
      managedBy = "home-manager";
      package = "jq";
      packageVersion = pkgs.jq.version;
      scope = "isolated-cli-poc";
    }
    + "\n";
}
