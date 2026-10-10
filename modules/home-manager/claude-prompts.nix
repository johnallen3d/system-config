# Claude Code slash commands and subagent role definitions, per profile.
#
# Mirrors pi-prompts.nix: personal prompts → claude-personal, work prompts → claude-gmatter.
# Subagent role definitions are shared — canonical copy lives in claude-personal/agents,
# and claude-gmatter/agents is a symlink to it (mirrors pi-work/themes → pi/themes in
# pi-settings.nix). Split the symlink later if a profile needs to diverge.
#
# Roles select family aliases, never provider/version-specific model IDs.
# In work, subscription-proxy.nix owns the ANTHROPIC_DEFAULT_*_MODEL targets;
# these must be advertised by the live work gateway (verified by
# tests/subscription-proxy-claude.py). Personal uses its own alias defaults.
{
  lib,
  pkgs,
  ...
}: let
  # Standalone agent-kit presentation: no plugin, auth, or profile-state lookup.
  # Both profiles use this renderer so plugin upgrades cannot split their UI.
  claudeStatusLine = pkgs.writeShellApplication {
    name = "claude-statusline";
    runtimeInputs = [pkgs.git pkgs.nodejs_24];
    text = ''exec node ${./claude-statusline/statusline.mjs}'';
  };
  footerSettings = {
    statusLine = {
      type = "command";
      command = "${claudeStatusLine}/bin/claude-statusline";
      padding = 0;
    };
  };
  workSettings = footerSettings // {outputStyle = "ELI5";};
in {
  home.file = {
    # Personal prompts → ~/.config/claude-personal/commands/
    ".config/claude-personal/commands/pkg-install.md".source = ./claude-prompts/pkg-install.md;
    ".config/claude-personal/commands/wrap.md".source = ./claude-prompts/wrap.md;

    # Work-local prompts not shipped by the agent-kit plugin.
    ".config/claude-gmatter/commands/implement.md".source = ./claude-prompts/implement.md;
    ".config/claude-gmatter/commands/issue-plan.md".source = ./claude-prompts/issue-plan.md;
    ".config/claude-gmatter/commands/issue-review.md".source = ./claude-prompts/issue-review.md;
    ".config/claude-gmatter/output-styles/ELI5.md".source = ./claude-output-styles/ELI5.md;

    # Shared subagent role definitions — canonical copy under claude-personal.
    ".config/claude-personal/agents/scout.md".source = ./claude-agents/scout.md;
    ".config/claude-personal/agents/researcher.md".source = ./claude-agents/researcher.md;
    ".config/claude-personal/agents/planner.md".source = ./claude-agents/planner.md;
    ".config/claude-personal/agents/worker.md".source = ./claude-agents/worker.md;
    ".config/claude-personal/agents/reviewer.md".source = ./claude-agents/reviewer.md;
  };

  # The plugin owns agent-kit skills and commands. Remove only the links made
  # by the former checkout bridge; leave local and Home Manager entries alone.
  home.activation.claudeAgentKitLinkMigration = lib.hm.dag.entryAfter ["claudeGmatterAgentKit"] ''
    for dir in "$HOME/.config/claude-gmatter/skills" "$HOME/.config/claude-gmatter/commands"; do
      [ -d "$dir" ] || continue
      for entry in "$dir"/*; do
        [ -L "$entry" ] || continue
        case "$(readlink "$entry")" in
          "$HOME/dev/src/amfaro/pi-workflows/skills/"*|\
          "$HOME/dev/src/amfaro/pi-workflows/prompts/"*|\
          "$HOME/dev/src/amfaro/agent-kit/skills/"*|\
          "$HOME/dev/src/amfaro/agent-kit/prompts/"*)
            $DRY_RUN_CMD rm -f "$entry"
            ;;
        esac
      done
    done
  '';

  # Claude keeps its own plugin state under the work profile. Install once,
  # leaving marketplace/plugin updates to Claude rather than every rebuild.
  home.activation.claudeGmatterAgentKit = lib.hm.dag.entryAfter ["claudeCodeSymlink"] (
    if pkgs.stdenv.hostPlatform.isDarwin
    then ''
      export CLAUDE_CONFIG_DIR="$HOME/.config/claude-gmatter"
      claude="$HOME/.local/bin/claude"
      if ! "$claude" plugin marketplace list --json | ${pkgs.jq}/bin/jq -e 'any(.[]; .name == "amfaro")' >/dev/null; then
        $DRY_RUN_CMD "$claude" plugin marketplace add amfaro/agent-kit
      fi
      if ! "$claude" plugin list --json | ${pkgs.jq}/bin/jq -e 'any(.[]; .id == "agent-kit@amfaro")' >/dev/null; then
        $DRY_RUN_CMD "$claude" plugin install agent-kit@amfaro --scope user
      fi
    ''
    else ''
      echo "Work agent-kit: run agent-work-setup after configuring GitHub access."
    ''
  );

  # Remove stale directory-symlinks before home.file writes individual files.
  # Matches the pattern in pi-prompts.nix:9-17.
  home.activation.claudePromptDirMigration = lib.hm.dag.entryBefore ["writeBoundary"] ''
    for p in \
      "$HOME/.config/claude-personal/commands" \
      "$HOME/.config/claude-gmatter/commands" \
      "$HOME/.config/claude-personal/agents" \
      "$HOME/.config/claude-gmatter/agents"; do
      if [ -L "$p" ]; then
        rm -f "$p"
      fi
    done
  '';

  # Work profile shares the personal agents/ directory via symlink.
  # Mirrors pi-settings.nix:131-132 (pi-work/themes → pi/themes).
  home.activation.claudeGmatterAgentsLink = lib.hm.dag.entryAfter ["linkGeneration"] ''
    ln -sfn "$HOME/.config/claude-personal/agents" "$HOME/.config/claude-gmatter/agents"
  '';

  # Share only the footer with personal; ELI5 remains a work-only setting.
  # Replace statusLine completely, preserving every unrelated user-owned key.
  home.activation.claudeGmatterSettings = lib.hm.dag.entryAfter ["writeBoundary" "claudeProfileDefaults"] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      for profile in claude-personal claude-gmatter; do
        settings="$HOME/.config/$profile/settings.json"
        managed=${lib.escapeShellArg (builtins.toJSON footerSettings)}
        if [ "$profile" = claude-gmatter ]; then
          managed=${lib.escapeShellArg (builtins.toJSON workSettings)}
        fi
        mkdir -p "$(dirname "$settings")"
        if [ ! -e "$settings" ]; then
          printf '%s\n' '{}' > "$settings"
        fi
        tmp="$(${pkgs.coreutils}/bin/mktemp "$settings.XXXXXX")"
        if ${pkgs.jq}/bin/jq --argjson managed "$managed" \
          '. + $managed' "$settings" > "$tmp"; then
          chmod 0600 "$tmp"
          mv "$tmp" "$settings"
        else
          rm -f "$tmp"
          exit 1
        fi
      done
    fi
  '';
}
