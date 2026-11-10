# Personal-only Traces integrations, vendored from `traces setup` v0.6.45.
# Authentication and the local database stay host-local; folder-sharing rules
# are declared here.
{
  config,
  lib,
  pkgs,
  ...
}: let
  home = config.home.homeDirectory;
  traces = import ./packages/traces.nix {inherit pkgs;};
  tracesBin = lib.getExe traces;
  # Traces ignores CLAUDE_CONFIG_DIR and hardcodes Pi discovery to ~/.pi/agent.
  claudeDir = "${home}/.config/claude-personal";
  piSessions = "${home}/.config/pi/sessions";
  # Traces keys share rules by the first 12 hex chars of sha256(API URL).
  tracesConfigDir =
    if pkgs.stdenv.hostPlatform.isDarwin
    then "Library/Preferences/traces"
    else ".config/traces";
  shareFile = "share-${builtins.substring 0 12 (builtins.hashString "sha256" "https://actions.traces.com")}.json";
  personalNamespace = {
    id = "k972xspteyrdfjc4getqaf9dex8ht790";
    slug = "johnallen3d";
    type = "individual";
  };
  shareRules = {
    "//" = "Managed by system-config modules/home-manager/traces.nix.";
    rules = {
      "${home}/dev/src/playground/switchyard" = personalNamespace;
    };
  };
  piExtension = name:
    pkgs.writeText name (lib.replaceStrings ["@traces@"] [tracesBin]
      (builtins.readFile (./traces/pi + "/${name}")));
  sessionEnv = pkgs.writeShellApplication {
    name = "traces-session-env";
    runtimeInputs = [pkgs.coreutils pkgs.jq];
    text = builtins.readFile ./traces/claude/traces-session-env.sh;
  };
  hook = command: {
    type = "command";
    inherit command;
    timeout = 5;
  };
  agentHook = event: hook "TRACES_CLAUDE_DIR=${lib.escapeShellArg claudeDir} ${tracesBin} hook agent ${event} --agent claude-code";
  claudeHooks = {
    SessionStart = [
      {
        matcher = "";
        hooks = [
          (hook "${config.home.homeDirectory}/.config/claude-personal/hooks/traces-session-env.sh")
          (agentHook "session-start")
        ];
      }
    ];
    UserPromptSubmit = [
      {
        matcher = "";
        hooks = [(agentHook "prompt-submitted")];
      }
    ];
    Stop = [
      {
        matcher = "";
        hooks = [(agentHook "agent-done")];
      }
    ];
    SessionEnd = [
      {
        matcher = "";
        hooks = [(agentHook "session-end")];
      }
    ];
  };
in {
  home.file = {
    ".config/pi/extensions/traces.ts".source = piExtension "traces.ts";
    ".config/pi/extensions/traces-agent-hooks.ts".source = piExtension "traces-agent-hooks.ts";
    ".config/pi/prompts/share-to-traces.md".source = ./traces/pi/share-to-traces.md;
    ".config/pi/skills/share-to-traces-pi/SKILL.md".source = ./traces/pi/skills/share-to-traces-pi/SKILL.md;
    ".config/claude-personal/commands/share-to-traces.md".source = ./traces/claude/share-to-traces.md;
    ".config/claude-personal/skills/share-to-traces/SKILL.md".source = ./traces/claude/skills/share-to-traces/SKILL.md;
    ".config/claude-personal/hooks/traces-session-env.sh" = {
      source = "${sessionEnv}/bin/traces-session-env";
      executable = true;
    };
    "${tracesConfigDir}/${shareFile}".text = builtins.toJSON shareRules;
  };

  home.sessionVariables.TRACES_CLAUDE_DIR = claudeDir;

  # Point Traces' fixed Pi discovery path at personal Pi sessions. Legacy
  # sessions are moved aside, never deleted.
  home.activation.tracesPiSessions = lib.hm.dag.entryAfter ["writeBoundary"] ''
    legacy="$HOME/.pi/agent/sessions"
    if [ -e "$legacy" ] && [ ! -L "$legacy" ]; then
      run mv "$legacy" "$legacy.pre-traces-$(${pkgs.coreutils}/bin/date +%Y%m%d%H%M%S)"
    fi
    run mkdir -p ${lib.escapeShellArg piSessions} "$HOME/.pi/agent"
    run ln -sfn ${lib.escapeShellArg piSessions} "$legacy"
  '';

  # Own only Traces registrations in the writable personal settings file.
  # Refresh commands on upgrades without duplicating them or removing other hooks.
  home.activation.tracesPersonalClaudeHooks = lib.hm.dag.entryAfter ["linkGeneration" "claudeGmatterSettings" "rexClaudeHooks"] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      (
        settings="$HOME/.config/claude-personal/settings.json"
        if [ -L "$settings" ]; then
          echo "Refusing to replace symlinked Claude personal settings" >&2
          exit 1
        fi
        mkdir -p "$(dirname "$settings")"
        [ -e "$settings" ] || printf '%s\n' '{}' > "$settings"
        tmp="$(${pkgs.coreutils}/bin/mktemp "$settings.traces-XXXXXX")"
        trap 'rm -f "$tmp"' EXIT
        ${pkgs.jq}/bin/jq -e --argjson managed ${lib.escapeShellArg (builtins.toJSON claudeHooks)} '
          reduce ($managed | keys[]) as $event (.;
            .hooks[$event] = (
              ((.hooks[$event] // []) | map(
                .hooks |= map(select(
                  (.type == "command" and ((.command // "") |
                    test("(^|/)traces hook agent |traces-session-env"))) | not))
                | select((.hooks // []) | length > 0)))
              + $managed[$event]
            )
          )
        ' "$settings" > "$tmp"
        chmod 0600 "$tmp"
        mv "$tmp" "$settings"
      )
    fi
  '';
}
