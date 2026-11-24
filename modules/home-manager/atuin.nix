{
  config,
  lib,
  pkgs,
  ...
}: let
  home = config.home.homeDirectory;
  # The daemon captures one Claude Code and one Pi root, read from its own
  # environment. Pin it to the personal profiles; work and notes profiles stay
  # out of this store.
  agentDirs = {
    CLAUDE_CONFIG_DIR = "${home}/.config/claude-personal";
    PI_CODING_AGENT_DIR = "${home}/.config/pi";
  };
in {
  # Local-only shell history. fish binds Ctrl+R to Atuin (replacing tv's history
  # search); zsh and bash keep their own Ctrl+R, since tv never handled it there.
  # Up stays with the shell, and `?` is not bound to hosted Atuin AI.
  # The daemon (launchd on macOS, socket-activated systemd user unit on Linux)
  # captures agent threads and syncs history and threads to the tailnet-only
  # server on nas (pi-cielo hosts/nas/atuin). Sync starts after a one-time
  # interactive `atuin login` per host; the key and password stay out of Nix.
  programs.atuin = {
    enable = true;
    flags = ["--disable-up-arrow" "--disable-ai" "--disable-ctrl-r"];
    daemon.enable = true;
    settings = {
      # Atuin 18.24 always uses records sync, so there is no sync.records.
      sync_address = "https://nas.taila14c2.ts.net:8889";
      auto_sync = true;
      update_check = false;
      threads.capture = true;
      # Clients find the socket-activated socket through XDG_RUNTIME_DIR, which
      # SSH shells on Miller and Drummer lack. Pin it (johna is uid 1000).
      daemon.socket_path = lib.mkIf pkgs.stdenv.isLinux "/run/user/1000/atuin.sock";
    };
  };

  launchd.agents.atuin-daemon.config.EnvironmentVariables = agentDirs;
  # Home Manager's macOS socket lives here; the daemon won't create the dir.
  xdg.dataFile."atuin/.keep" = lib.mkIf pkgs.stdenv.isDarwin {text = "";};

  systemd.user.services.atuin-daemon.Service.Environment =
    builtins.attrValues (builtins.mapAttrs (name: value: "${name}=${value}") agentDirs);
}
