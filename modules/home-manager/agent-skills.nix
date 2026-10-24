{
  lib,
  pkgs,
  ...
}: let
  skill = ./agent-skills/authoring-commits/SKILL.md;
  targets = [
    ".config/pi/skills/authoring-commits/SKILL.md"
    ".config/claude-personal/skills/authoring-commits/SKILL.md"
  ];
in {
  # Personal policy must not enter global discovery or either work profile.
  # Manage files, not whole skill directories or mutable plugin/package caches.
  home.file = lib.genAttrs targets (_: {source = skill;});

  # Personal Claude used to alias the entire shared skills directory. Preserve
  # access to its other shared skills without putting personal skills there.
  home.activation.personalClaudeSharedSkills = lib.hm.dag.entryAfter ["linkGeneration"] ''
    for shared in "$HOME/.agents/skills/"*; do
      [ -e "$shared" ] || continue
      name="''${shared##*/}"
      [ "$name" != authoring-commits ] || continue
      target="$HOME/.config/claude-personal/skills/$name"
      if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        $DRY_RUN_CMD ln -s "$shared" "$target"
      fi
    done
  '';

  # The only reviewed unmanaged copy is personal Pi on Mac. Preserve it before
  # Home Manager checks for collisions; reject drift rather than forcing links.
  home.activation.authoringCommitsSkillMigration = lib.hm.dag.entryBefore ["checkLinkTargets"] ''
    # Retire only a verified managed global copy, including a personal link
    # written through the old Claude directory alias during an earlier switch.
    global_skill="$HOME/.agents/skills/authoring-commits/SKILL.md"
    if [ -e "$global_skill" ] || [ -L "$global_skill" ]; then
      link_target="$(${pkgs.coreutils}/bin/readlink "$global_skill" || true)"
      case "$link_target" in
        /nix/store/*-home-manager-files/.agents/skills/authoring-commits/SKILL.md|/nix/store/*-home-manager-files/.config/claude-personal/skills/authoring-commits/SKILL.md)
          if ${pkgs.diffutils}/bin/cmp -s "$global_skill" ${skill}; then
            $DRY_RUN_CMD rm -f "$global_skill"
          else
            echo "Refusing modified global commit skill: $global_skill" >&2
            exit 1
          fi
          ;;
        *)
          echo "Refusing unmanaged global commit skill: $global_skill" >&2
          exit 1
          ;;
      esac
    fi

    if [ -n "''${DRY_RUN:-}" ] || [ -n "''${DRY_RUN_CMD:-}" ]; then
      ${pkgs.python3}/bin/python3 ${./agent-skills/migrate-authoring-commits.py} "$HOME" --dry-run
    else
      ${pkgs.python3}/bin/python3 ${./agent-skills/migrate-authoring-commits.py} "$HOME"
    fi
  '';
}
