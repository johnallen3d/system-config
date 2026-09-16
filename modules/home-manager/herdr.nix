{
  config,
  lib,
  pkgs,
  ...
}: let
  herdr = "${pkgs.herdr}/bin/herdr";
  herdrSkill = pkgs.runCommand "herdr-skill-${pkgs.herdr.version}" {} ''
    mkdir -p "$out"
    cp -R ${pkgs.herdr.src}/skills/herdr/. "$out/"
  '';
  herdrWorktrunk = pkgs.fetchFromGitHub {
    owner = "devashish2203";
    repo = "herdr-worktrunk";
    rev = "v0.7.0";
    hash = "sha256-Tx++zTQ1z4H8dLdCjOZ1yX9QGY/i6M3Yvi39KGHDoH4=";
  };
  homeDir = config.home.homeDirectory;
  skillTargets = [
    ".agents/skills/herdr"
    ".config/pi/skills/herdr"
    ".config/pi-work/skills/herdr"
    ".config/claude-gmatter/skills/herdr"
  ];
in {
  # Keep one package-versioned Herdr skill available globally, in both custom
  # Pi profiles, and in the work Claude profile. The personal Claude profile
  # shares the global skills directory below.
  home.file =
    lib.genAttrs skillTargets (_: {source = herdrSkill;})
    // {
      ".config/claude-personal/skills".source =
        config.lib.file.mkOutOfStoreSymlink "${homeDir}/.agents/skills";
    };

  # Replace the mutable copy created by `npx skills add herdrdev/herdr -g` only
  # when it still matches Herdr's bundled skill. Preserve modified copies so
  # Home Manager reports the collision instead of deleting local changes.
  home.activation.herdrSkillMigration = lib.hm.dag.entryBefore ["writeBoundary"] ''
    global_skill="${homeDir}/.agents/skills/herdr"
    if [ -d "$global_skill" ] && [ ! -L "$global_skill" ]; then
      if ${pkgs.diffutils}/bin/diff -qr "$global_skill" ${herdrSkill} >/dev/null; then
        $DRY_RUN_CMD rm -rf "$global_skill"
      else
        echo "Refusing to replace modified Herdr skill at $global_skill" >&2
        exit 1
      fi
    fi

    personal_skills="${homeDir}/.config/claude-personal/skills"
    if [ -L "$personal_skills" ]; then
      link_target="$(${pkgs.coreutils}/bin/readlink "$personal_skills")"
      if [ "$link_target" = "${homeDir}/.agents/skills" ] || [ "$link_target" = "${homeDir}/.agents/skills/" ]; then
        $DRY_RUN_CMD rm -f "$personal_skills"
      fi
    fi
  '';

  # Herdr resolves integrations from the active agent profile environment.
  # Install into both personal/work Pi and Claude profile pairs after their
  # mutable settings files have been initialized.
  home.activation.herdrIntegrations = lib.hm.dag.entryAfter ["piSettings" "piWorkSettings"] ''
    ${herdr} plugin link ${herdrWorktrunk} --enabled

    for profile in "${homeDir}/.config/pi" "${homeDir}/.config/pi-work"; do
      PI_CODING_AGENT_DIR="$profile" ${herdr} integration install pi
    done

    for profile in "${homeDir}/.config/claude-personal" "${homeDir}/.config/claude-gmatter"; do
      CLAUDE_CONFIG_DIR="$profile" ${herdr} integration install claude
    done
  '';
}
