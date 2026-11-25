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

  # Work threads (claude-gmatter + pi-work) live in a second, local-only store
  # under its own ATUIN_HOME: separate config file, data dir, socket and daemon.
  # Its config has no sync_address and it is never logged in, so nothing in it
  # can reach the synced personal store on nas. Notes (pi-notes) is not captured.
  atuin = config.programs.atuin.package;
  workHome = "${home}/.atuin-work";
  workAgentDirs = {
    CLAUDE_CONFIG_DIR = "${home}/.config/claude-gmatter";
    PI_CODING_AGENT_DIR = "${home}/.config/pi-work";
  };
  workEnv = workAgentDirs // {ATUIN_HOME = workHome;};
  # Resume in the work profile with the amfaro mise env (agent-projects.nix),
  # since the picker runs outside the project's mise activation.
  workResumeEnv =
    "env -u ANTHROPIC_API_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY"
    + " CLAUDE_CONFIG_DIR=${workAgentDirs.CLAUDE_CONFIG_DIR}"
    + " PI_CODING_AGENT_DIR=${workAgentDirs.PI_CODING_AGENT_DIR}"
    + " PI_MODEL_ROUTER_JEV_MODE=primary";
  workConfig = (pkgs.formats.toml {}).generate "atuin-work-config.toml" {
    auto_sync = false;
    update_check = false;
    daemon = {
      enabled = true;
      socket_path = "${workHome}/daemon.sock";
      pidfile_path = "${workHome}/data/atuin-daemon.pid";
    };
    threads = {
      capture = true;
      resume = {
        claude = "${workResumeEnv} claude --resume {id}";
        pi = "${workResumeEnv} pi --session {id}";
      };
    };
  };
  # The only client entry point to the work store; plain `atuin` stays personal.
  atuinWork = pkgs.writeShellApplication {
    name = "atuin-work";
    text = ''
      export ATUIN_HOME=${lib.escapeShellArg workHome}
      exec ${atuin}/bin/atuin "$@"
    '';
  };
  workCommand = "${atuin}/bin/atuin daemon start";

  # Read-only MCP servers (`atuin mcp`, stdio) for agents, one per store. Each
  # drops every inherited ATUIN_* variable before choosing its store, so a
  # personal agent started with ATUIN_HOME pointing at the work store (or the
  # reverse) still reaches only its own profile's threads and history.
  mkAtuinMcp = name: storeSetup:
    pkgs.writeShellApplication {
      inherit name;
      text = ''
        for var in "''${!ATUIN_@}"; do
          unset "$var"
        done
        ${storeSetup}
        exec ${atuin}/bin/atuin mcp
      '';
    };
  personalMcp = mkAtuinMcp "atuin-mcp-personal" "";
  workMcp = mkAtuinMcp "atuin-mcp-work" "export ATUIN_HOME=${lib.escapeShellArg workHome}";
in {
  # Registered by claude-prompts.nix and pi-settings.nix for each profile.
  options.atuin.mcpServers = lib.mkOption {
    type = lib.types.attrsOf lib.types.attrs;
    readOnly = true;
    internal = true;
    description = "Per-profile Atuin MCP server definitions (personal, work).";
  };

  config = {
    atuin.mcpServers = {
      personal.command = "${personalMcp}/bin/atuin-mcp-personal";
      work.command = "${workMcp}/bin/atuin-mcp-work";
    };

    # Shell history. fish binds Ctrl+R to Atuin (replacing tv's history
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

    home.packages = [atuinWork];
    home.file.".atuin-work/config.toml".source = workConfig;

    launchd.agents.atuin-daemon.config.EnvironmentVariables = agentDirs;
    launchd.agents.atuin-work-daemon = {
      enable = true;
      config = {
        ProgramArguments = ["/bin/sh" "-c" "/bin/wait4path /nix/store && exec ${workCommand}"];
        EnvironmentVariables = workEnv;
        KeepAlive = {
          Crashed = true;
          SuccessfulExit = false;
        };
        ProcessType = "Background";
        RunAtLoad = true;
      };
    };
    # Home Manager's macOS socket lives here; the daemon won't create the dir.
    xdg.dataFile."atuin/.keep" = lib.mkIf pkgs.stdenv.isDarwin {text = "";};

    systemd.user.services.atuin-daemon.Service.Environment =
      lib.mapAttrsToList (name: value: "${name}=${value}") agentDirs;

    systemd.user.services.atuin-work-daemon = {
      Unit.Description = "Atuin daemon (work threads, local-only store)";
      Service = {
        ExecStart = workCommand;
        Environment = lib.mapAttrsToList (name: value: "${name}=${value}") workEnv;
        Restart = "on-failure";
        RestartSec = 5;
      };
      Install.WantedBy = ["default.target"];
    };
  };
}
