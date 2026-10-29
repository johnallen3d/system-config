{
  config,
  lib,
  pkgs,
  ...
}: let
  skill = ./agent-skills/authoring-commits/SKILL.md;
  # Keep Rex's upstream stub: the installed CLI supplies the current guide.
  rexSkill = ./agent-skills/rex/SKILL.md;
  rexClaudeTargets = map (profile: ".config/${profile}/skills/rex") [
    "claude-personal"
    "claude-gmatter"
  ];
  rexHook = {
    hooks = [
      {
        type = "command";
        command = "/bin/sh -c 'rex __internal session-start --agent claude 2>/dev/null || true'";
        timeout = 5;
      }
    ];
  };
  targets = [
    ".config/pi/skills/authoring-commits/SKILL.md"
    ".config/claude-personal/skills/authoring-commits/SKILL.md"
  ];
  # Personal-only procedures moved out of the always-loaded instructions.
  personalSkills = lib.concatMapAttrs (name: source: {
    ".config/pi/skills/${name}/SKILL.md".source = source;
    ".config/claude-personal/skills/${name}/SKILL.md".source = source;
  }) {
    delegating-to-subagents = ./agent-skills/delegating-to-subagents/SKILL.md;
    implementation-attribution = ./agent-skills/implementation-attribution/SKILL.md;
  };
in {
  # Personal policy must not enter global discovery or either work profile.
  # Manage files, not whole skill directories or mutable plugin/package caches.
  home.file =
    lib.genAttrs targets (_: {source = skill;})
    // personalSkills
    // {
      # Both Pi profiles discover this location without profile-local copies.
      ".agents/skills/rex/SKILL.md".source = rexSkill;
    }
    // lib.genAttrs rexClaudeTargets (_: {
      source = config.lib.file.mkOutOfStoreSymlink "${config.home.homeDirectory}/.agents/skills/rex";
    });

  # Adopt only the exact upstream stub and direct shared-directory links.
  # Foreign skills remain subject to Home Manager's normal collision checks.
  home.activation.rexSkillMigration = lib.hm.dag.entryBefore ["checkLinkTargets"] ''
    shared="$HOME/.agents/skills/rex/SKILL.md"
    if [ -e "$shared" ] && [ ! -L "$shared" ]; then
      if [ ! -f "$shared" ] || ! ${pkgs.diffutils}/bin/cmp -s "$shared" ${rexSkill}; then
        echo "Refusing modified Rex skill: $shared" >&2
        exit 1
      fi
      backup="$HOME/.local/state/system-config/skill-migrations/rex/SKILL.md"
      if [ -e "$backup" ] || [ -L "$backup" ]; then
        if [ -L "$backup" ] || ! ${pkgs.diffutils}/bin/cmp -s "$backup" "$shared"; then
          echo "Refusing conflicting Rex skill backup: $backup" >&2
          exit 1
        fi
      fi
      if [ -z "''${DRY_RUN_CMD:-}" ]; then
        mkdir -p "$(dirname "$backup")"
        [ -e "$backup" ] || cp -p "$shared" "$backup"
        rm "$shared"
      fi
    fi
    for profile in claude-personal claude-gmatter; do
      target="$HOME/.config/$profile/skills/rex"
      if [ -L "$target" ] && [ "$(readlink "$target")" = "$HOME/.agents/skills/rex" ]; then
        $DRY_RUN_CMD rm "$target"
      fi
    done
  '';

  # Settings remain writable. Add only a missing Rex hook, retaining every
  # unrelated hook/settings entry. Rex's hook is a no-op without its CLI.
  home.activation.rexClaudeHooks = lib.hm.dag.entryAfter ["writeBoundary" "claudeWorkContext"] ''
    if [ -z "''${DRY_RUN_CMD:-}" ]; then
      for profile in claude-personal claude-gmatter; do
        settings="$HOME/.config/$profile/settings.json"
        mkdir -p "$(dirname "$settings")"
        [ -e "$settings" ] || printf '%s\n' '{}' > "$settings"
        tmp="$(${pkgs.coreutils}/bin/mktemp "$settings.XXXXXX")"
        if ${pkgs.jq}/bin/jq --argjson rex ${lib.escapeShellArg (builtins.toJSON rexHook)} '
          .hooks.SessionStart //= [] |
          if any(.hooks.SessionStart[].hooks[]?;
            .type == "command" and .command == $rex.hooks[0].command)
          then . else .hooks.SessionStart += [$rex] end
        ' "$settings" > "$tmp"; then
          chmod 0600 "$tmp"
          mv "$tmp" "$settings"
        else
          rm -f "$tmp"
          exit 1
        fi
      done
    fi
  '';

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
