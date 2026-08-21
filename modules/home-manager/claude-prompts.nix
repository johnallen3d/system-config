# Claude Code slash commands and subagent role definitions, per profile.
#
# Mirrors pi-prompts.nix: personal prompts → claude-personal, work prompts → claude-gmatter.
# Subagent role definitions are shared — canonical copy lives in claude-personal/agents,
# and claude-gmatter/agents is a symlink to it (mirrors pi-work/themes → pi/themes in
# pi-settings.nix). Split the symlink later if a profile needs to diverge.
#
# Model mapping (pi.dev → Claude Code), used when porting prompt frontmatter:
#   gpt-5.6-terra       → opus    (Claude Opus 4.x family alias)
#   gpt-5.6-luna  → haiku   (Claude Haiku 4.x family alias)
{lib, pkgs, ...}: {
  home.file = {
    # Personal prompts → ~/.config/claude-personal/commands/
    ".config/claude-personal/commands/pkg-install.md".source = ./claude-prompts/pkg-install.md;
    ".config/claude-personal/commands/wrap.md".source = ./claude-prompts/wrap.md;

    # Work-local prompts not maintained by pi-workflows.
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

  # The checkout lives outside this flake, so discover new entries at activation
  # time instead of reading it during pure Nix evaluation.
  home.activation.claudePiWorkflowsLinks = lib.hm.dag.entryAfter ["writeBoundary"] ''
    pi_workflows="$HOME/dev/src/amfaro/pi-workflows"
    claude_workflows="$HOME/.config/claude-gmatter"
    mkdir -p "$claude_workflows/skills" "$claude_workflows/commands"

    link_workflows() {
      local source_dir="$1" target_dir="$2" pattern="$3" entry name target
      [ -d "$source_dir" ] || return 0
      for entry in "$source_dir"/$pattern; do
        [ -e "$entry" ] || continue
        name="$(basename "$entry")"
        target="$target_dir/$name"
        if [ ! -e "$target" ] || [ -L "$target" ]; then
          ln -sfn "$entry" "$target"
        fi
      done
    }

    link_workflows "$pi_workflows/skills" "$claude_workflows/skills" '*'
    link_workflows "$pi_workflows/prompts" "$claude_workflows/commands" '*.md'
  '';

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
  home.activation.claudeGmatterAgentsLink = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ln -sfn "$HOME/.config/claude-personal/agents" "$HOME/.config/claude-gmatter/agents"
  '';

  # Claude owns the rest of this runtime settings file; set only this profile default.
  home.activation.claudeGmatterOutputStyle = lib.hm.dag.entryAfter ["writeBoundary"] ''
    settings="$HOME/.config/claude-gmatter/settings.json"
    mkdir -p "$(dirname "$settings")"
    if [ -e "$settings" ]; then
      ${pkgs.jq}/bin/jq '.outputStyle = "ELI5"' "$settings" > "$settings.tmp"
    else
      printf '%s\n' '{"outputStyle":"ELI5"}' > "$settings.tmp"
    fi
    mv "$settings.tmp" "$settings"
  '';
}
