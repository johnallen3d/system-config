# Personal-only Traces integrations, vendored from `traces setup` v0.6.45.
# Authentication, folder-sharing rules, and the local database stay host-local.
{
  config,
  lib,
  pkgs,
  ...
}: let
  traces = import ./packages/traces.nix {inherit pkgs;};
  tracesBin = lib.getExe traces;
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
  agentHook = event: hook "${tracesBin} hook agent ${event} --agent claude-code";
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
  };

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
