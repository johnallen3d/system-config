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
  herdrWorktrunkSrc = pkgs.fetchFromGitHub {
    owner = "devashish2203";
    repo = "herdr-worktrunk";
    rev = "v0.7.0";
    hash = "sha256-Tx++zTQ1z4H8dLdCjOZ1yX9QGY/i6M3Yvi39KGHDoH4=";
  };
  herdrWorktrunk = pkgs.runCommand "herdr-worktrunk-0.7.0" {} ''
    cp -R ${herdrWorktrunkSrc}/. "$out"
    chmod -R u+w "$out"
    install -m755 ${./herdr-worktrunk-cleanup-gone.sh} "$out/cleanup-gone.sh"

    cat >> "$out/config.sh" <<'EOF'

    # Print the optional ref used as the base for branches created by the default
    # picker. An empty value preserves Worktrunk's default-branch behavior.
    worktrunk_create_base() {
      local value

      value=$(worktrunk_config_value create_base)
      printf '%s\n' "$value"
    }

    # Print "true" when opening the picker should clean up safe worktrees whose
    # configured upstream branch disappeared after fetching remote state.
    worktrunk_cleanup_deleted_upstreams() {
      local value

      value=$(worktrunk_config_value cleanup_deleted_upstreams)
      case "$value" in
        true)
          printf '%s\n' true
          ;;
        ""|false)
          printf '%s\n' false
          ;;
        *)
          printf '\033[33mWarning:\033[0m unsupported cleanup_deleted_upstreams %q; disabling cleanup\n' "$value" >&2
          printf '%s\n' false
          ;;
      esac
    }
    EOF

    substituteInPlace "$out/picker.sh" \
      --replace-fail \
        'source "$plugin_root/helpers.sh"' \
        'source "$plugin_root/helpers.sh"

    "$plugin_root/cleanup-gone.sh"

    # The current-branch action always uses @. Other picker variants may override
    # Worktrunk'"'"'s default branch with a configured ref such as origin/main.
    if [[ $create_base != @ ]]; then
      configured_create_base=$(worktrunk_create_base)
      if [[ -n $configured_create_base ]]; then
        create_base=$configured_create_base
        create_base_label=$configured_create_base
      fi
    fi'
  '';
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
