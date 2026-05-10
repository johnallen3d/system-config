# Claude Code slash commands and subagent role definitions, per profile.
#
# Mirrors pi-prompts.nix: personal prompts → claude-personal, work prompts → claude-gmatter.
# Subagent role definitions are shared — canonical copy lives in claude-personal/agents,
# and claude-gmatter/agents is a symlink to it (mirrors pi-work/themes → pi/themes in
# pi-settings.nix). Split the symlink later if a profile needs to diverge.
#
# Model mapping (pi.dev → Claude Code), used when porting prompt frontmatter:
#   gpt-5.4       → opus    (Claude Opus 4.x family alias)
#   gpt-5.4-mini  → haiku   (Claude Haiku 4.x family alias)
{lib, ...}: {
  # Personal prompts → ~/.config/claude-personal/commands/
  home.file.".config/claude-personal/commands/pkg-install.md".source = ./claude-prompts/pkg-install.md;
  home.file.".config/claude-personal/commands/wrap.md".source = ./claude-prompts/wrap.md;

  # Work prompts → ~/.config/claude-gmatter/commands/
  home.file.".config/claude-gmatter/commands/implement.md".source = ./claude-prompts/implement.md;
  home.file.".config/claude-gmatter/commands/issue-implement.md".source = ./claude-prompts/issue-implement.md;
  home.file.".config/claude-gmatter/commands/issue-plan.md".source = ./claude-prompts/issue-plan.md;
  home.file.".config/claude-gmatter/commands/issue-review.md".source = ./claude-prompts/issue-review.md;

  # Shared subagent role definitions — canonical copy under claude-personal.
  home.file.".config/claude-personal/agents/scout.md".source = ./claude-agents/scout.md;
  home.file.".config/claude-personal/agents/researcher.md".source = ./claude-agents/researcher.md;
  home.file.".config/claude-personal/agents/planner.md".source = ./claude-agents/planner.md;
  home.file.".config/claude-personal/agents/worker.md".source = ./claude-agents/worker.md;
  home.file.".config/claude-personal/agents/reviewer.md".source = ./claude-agents/reviewer.md;

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
}
