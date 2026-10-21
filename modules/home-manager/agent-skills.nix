{
  lib,
  pkgs,
  ...
}: let
  skill = ./agent-skills/authoring-commits/SKILL.md;
  targets = [
    ".agents/skills/authoring-commits/SKILL.md"
    ".config/pi/skills/authoring-commits/SKILL.md"
    ".config/pi-work/skills/authoring-commits/SKILL.md"
    ".config/claude-gmatter/skills/authoring-commits/SKILL.md"
  ];
in {
  # Personal Claude already shares ~/.agents/skills via herdr.nix. Manage only
  # this file, never whole skill directories or mutable plugin/package caches.
  home.file = lib.genAttrs targets (_: {source = skill;});

  # The only reviewed unmanaged copy is personal Pi on Mac. Preserve it before
  # Home Manager checks for collisions; reject drift rather than forcing links.
  home.activation.authoringCommitsSkillMigration = lib.hm.dag.entryBefore ["checkLinkTargets"] ''
    if [ -n "''${DRY_RUN:-}" ] || [ -n "''${DRY_RUN_CMD:-}" ]; then
      ${pkgs.python3}/bin/python3 ${./agent-skills/migrate-authoring-commits.py} "$HOME" --dry-run
    else
      ${pkgs.python3}/bin/python3 ${./agent-skills/migrate-authoring-commits.py} "$HOME"
    fi
  '';
}
