# Claude Code side of the daily-note "## Agent Log". Pi writes the same list
# through its session-capture extension; `agent-log` reuses that code so both
# harnesses share one chronological list, tagged #claude or #pi.
{
  config,
  lib,
  pkgs,
  ...
}: let
  vaultPath = config.home.sessionVariables.PI_SESSION_CAPTURE_VAULT_PATH or null;
  source = lib.cleanSourceWith {
    src = ./pi/extensions/session-capture;
    filter = path: _type: let
      name = builtins.baseNameOf (toString path);
    in
      name == "index.ts" || name == "agent-log.ts";
  };
  agentLog = pkgs.writeShellApplication {
    name = "agent-log";
    runtimeInputs = [pkgs.nodejs_24];
    text = ''
      ${lib.optionalString (vaultPath != null) ''
        export PI_SESSION_CAPTURE_VAULT_PATH="''${PI_SESSION_CAPTURE_VAULT_PATH:-${vaultPath}}"
      ''}
      exec node --no-warnings ${source}/agent-log.ts "$@"
    '';
  };
  # SessionStart output becomes context, like Pi's before_agent_start prompt.
  instructions = pkgs.writeText "agent-log-instructions" ''
    Agent journal capture:
    - After finishing a meaningful piece of work (fix, feature, decision, or finding worth remembering), run `agent-log "<summary>"` once for it, before your final response.
    - Summary must be one short journal bullet, about 8-14 words. No details.
    - Capture outcome/decision only; omit validation, commit hash, file list, tool output, skill lists, and agent inventory.
    - Good: "Pinned Home Manager to release-26.05 to fix rebuild warning".
    - Bad: "Available executable agents: 17" or "fix the bugs".
    - If no meaningful work happened (questions, exploration, aborted turns), do not run agent-log.
  '';
  sessionStart = pkgs.writeShellScript "agent-log-session-start" "cat ${instructions}";
  hook = {
    matcher = "";
    hooks = [
      {
        type = "command";
        command = "${sessionStart}";
        timeout = 5;
      }
    ];
  };
in {
  home.packages = [agentLog];

  # Own only the agent-log hook and permission in each profile's writable
  # settings (work entries are tagged #work); leave other entries alone.
  home.activation.agentLogClaudeHooks = lib.hm.dag.entryAfter ["linkGeneration" "claudeGmatterSettings" "rexClaudeHooks" "tracesPersonalClaudeHooks"] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      for profile in claude-personal claude-gmatter; do (
        settings="$HOME/.config/$profile/settings.json"
        mkdir -p "$(dirname "$settings")"
        [ -e "$settings" ] || printf '%s\n' '{}' > "$settings"
        tmp="$(${pkgs.coreutils}/bin/mktemp "$settings.agent-log-XXXXXX")"
        trap 'rm -f "$tmp"' EXIT
        ${pkgs.jq}/bin/jq -e --argjson hook ${lib.escapeShellArg (builtins.toJSON hook)} '
          .hooks.SessionStart = (
            ((.hooks.SessionStart // []) | map(
              .hooks |= map(select(((.command // "") | contains("agent-log-session-start")) | not))
              | select((.hooks // []) | length > 0)))
            + [$hook]
          )
          | .permissions.allow = ((.permissions.allow // []) + ["Bash(agent-log:*)"] | unique)
        ' "$settings" > "$tmp"
        chmod 0600 "$tmp"
        mv "$tmp" "$settings"
      ) || exit 1; done
    fi
  '';
}
