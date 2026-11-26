# Antigravity CLI (agy) for personal work on the Mac and Omarchy only. agy has
# no profiles, so it is never installed on work-only hosts. It runs in
# enterprise-gateway mode against the personal subscription proxy, whose
# Antigravity login lives on Omarchy: no Google credential on any client.
{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.antigravity;
  # Google's release bucket, ahead of nixpkgs-unstable (1.5.13 adds Gemini 4
  # Neon through a gateway). Drop this override once nixpkgs has >= 1.5.13.
  buildId = "5999302598852608";
  sources = {
    aarch64-darwin = {
      platform = "darwin-arm/cli_mac_arm64.tar.gz";
      hash = "sha256-HIPj6Ii1QQxEptilRn9+yg11xNVVHIAHa32o3Hc4vZw=";
    };
    x86_64-linux = {
      platform = "linux-x64/cli_linux_x64.tar.gz";
      hash = "sha256-f6nMbfDQlWJpPWN8QGqGwbD1KrM2RxSx/S15zGBg1LI=";
    };
  };
  source = sources.${pkgs.stdenv.hostPlatform.system};
  unwrapped =
    if lib.versionAtLeast pkgs.antigravity-cli.version "1.5.13"
    then pkgs.antigravity-cli
    else
      pkgs.antigravity-cli.overrideAttrs (finalAttrs: _: {
        version = "1.5.13";
        src = pkgs.fetchurl {
          url = "https://storage.googleapis.com/antigravity-public/antigravity-cli/${finalAttrs.version}-${buildId}/${source.platform}";
          inherit (source) hash;
        };
      });
  # No fallback to a direct Google login: without the proxy key, agy stops.
  agy = pkgs.writeShellApplication {
    name = "agy";
    text = ''
      if ! key="$(${config.home.homeDirectory}/.local/bin/subscription-proxy client-key personal)" || [ -z "$key" ]; then
        echo "agy: personal subscription-proxy client key unavailable; not starting." >&2
        exit 1
      fi
      export AGY_LLM_GATEWAY_URL=${lib.escapeShellArg cfg.gatewayUrl}
      export AGY_LLM_GATEWAY_API_KEY="$key"
      exec ${lib.getExe unwrapped} "$@"
    '';
  };
  mcpServers =
    {
      switchyard.serverUrl = cfg.switchyardMcpUrl;
    }
    // lib.optionalAttrs config.executor.enable {
      executor.serverUrl = config.executor.mcpUrl;
    };
  # Personal instructions, skills, and prompts directly under ~/.gemini/config
  # (not a plugin): agy namespaces plugin skills as /<plugin>:<skill>, which
  # keeps bare /wrap from submitting on Enter and breaks tab completion.
  # agy has no slash-command prompts, so Claude's prompts become argument-free skills.
  skillsDir = ".gemini/config/skills";
  prompt = name: description: let
    file = config.home.file.".config/claude-personal/commands/${name}.md";
    raw =
      if file.text != null
      then file.text
      else builtins.readFile file.source;
    body = lib.concatStringsSep "\n---\n" (lib.drop 2 (lib.splitString "\n---\n" ("\n" + raw)));
    args = "the text John gave after the skill name (empty if none)";
  in ''
    ---
    name: ${name}
    description: ${builtins.toJSON description}
    ---
    ${builtins.replaceStrings ["$ARGUMENTS"] [args] body}
  '';
  personalSkills = {
    authoring-commits.source = ./agent-skills/authoring-commits/SKILL.md;
    delegating-to-subagents.source = ./agent-skills/delegating-to-subagents/SKILL.md;
    implementation-attribution.source = ./agent-skills/implementation-attribution/SKILL.md;
    shepherd.source = ./agent-skills/shepherd/SKILL.md;
    wrap.text = prompt "wrap" "Use only when John invokes /wrap: commit, integrate, push, and clean up personal work.";
    pkg-install.text = prompt "pkg-install" "Use when John invokes /pkg-install to install a package via the optimal method.";
  };
in {
  options.antigravity = {
    enable = lib.mkEnableOption "agy routed through the personal subscription proxy";
    gatewayUrl = lib.mkOption {
      type = lib.types.str;
      default = "https://omarchy.taila14c2.ts.net:8443";
      description = "Tailscale Serve HTTPS front of the personal proxy (agy rejects remote plain HTTP).";
    };
    switchyardMcpUrl = lib.mkOption {
      type = lib.types.str;
      default = (import ./switchyard-mcp.nix).url;
      description = "Switchyard MCP endpoint for spawned agy tasks. No X-Rex-* headers: agy does not expand them.";
    };
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = config.subscriptionProxy.enable;
        message = "antigravity needs subscriptionProxy clients for the personal key.";
      }
    ];
    home.packages = [agy];
    home.file =
      {
        ".gemini/config/AGENTS.md".text = config.home.file.".config/pi/AGENTS.md".text;
      }
      // lib.mapAttrs' (name: file: lib.nameValuePair "${skillsDir}/${name}/SKILL.md" file) personalSkills;
    # Clear any shared-skills mirror link whose name is now managed as a
    # personal skill before Home Manager checks for target collisions.
    home.activation.antigravityPersonalSkillMigration = lib.hm.dag.entryBefore ["checkLinkTargets"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        shared="$HOME/.agents/skills" dest="$HOME/.gemini/config/skills"
        for name in ${lib.escapeShellArgs (builtins.attrNames personalSkills)}; do
          link="$dest/$name/SKILL.md"
          [ -L "$link" ] || continue
          case "$(readlink "$link")" in "$shared"/*) ;; *) continue ;; esac
          rm "$link"; rmdir "$(dirname "$link")" 2>/dev/null || true
        done
      fi
    '';
    # Mirror Pi's shared ~/.agents/skills (host-specific, partly unmanaged) as
    # per-file links: agy ignores skills.json and skips directory symlinks.
    # Touch only links into ~/.agents/skills; managed personal skills win.
    home.activation.antigravitySharedSkills = lib.hm.dag.entryAfter ["linkGeneration"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        shared="$HOME/.agents/skills" dest="$HOME/.gemini/config/skills"
        for link in "$dest"/*/SKILL.md; do
          [ -L "$link" ] || continue
          case "$(readlink "$link")" in "$shared"/*) ;; *) continue ;; esac
          [ -e "$link" ] && continue
          rm "$link"; rmdir "$(dirname "$link")" 2>/dev/null || true
        done
        for skill in "$shared"/*/SKILL.md; do
          [ -e "$skill" ] || continue
          name="$(basename "$(dirname "$skill")")"
          target="$dest/$name/SKILL.md"
          if [ -e "$target" ] || [ -L "$target" ]; then
            [ -L "$target" ] || continue
            case "$(readlink "$target")" in "$shared"/*) ;; *) continue ;; esac
          fi
          mkdir -p "$dest/$name"
          ln -sfn "$skill" "$target"
        done
      fi
    '';
    # Merge only the switchyard server into agy's MCP config; agy and the user
    # own the rest. settings.json is left writable for Switchyard's
    # trustedWorkspaces and interactive /model or /effort changes.
    home.activation.antigravityMcp = lib.hm.dag.entryAfter ["linkGeneration"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        ${pkgs.python3}/bin/python3 - "$HOME/.gemini/config/mcp_config.json" ${lib.escapeShellArg (builtins.toJSON mcpServers)} <<'EOF'
      import json, os, sys
      path, servers = sys.argv[1], json.loads(sys.argv[2])
      try:
          with open(path) as f:
              text = f.read()
      except FileNotFoundError:
          text = ""
      data = json.loads(text) if text.strip() else {}
      merged = dict(data, mcpServers={**data.get("mcpServers", {}), **servers})
      if merged != data:
          os.makedirs(os.path.dirname(path), exist_ok=True)
          tmp = path + ".tmp"
          with open(tmp, "w") as f:
              json.dump(merged, f, indent=2)
              f.write("\n")
          os.replace(tmp, path)
      EOF
      fi
    '';
    # Default bare agy sessions to Gemini 4 Neon (High) only when no model is
    # saved yet or when migrating the old bare "Gemini 4 Neon" label (which
    # bypassed /effort once suffixed variants were exposed). Later /model and
    # /effort choices are preserved.
    home.activation.antigravityDefaultModel = lib.hm.dag.entryAfter ["linkGeneration"] ''
      if [ -z "''${DRY_RUN:-}" ]; then
        ${pkgs.python3}/bin/python3 - "$HOME/.gemini/antigravity-cli/settings.json" <<'EOF'
      import json, os, sys
      path = sys.argv[1]
      try:
          with open(path) as f:
              text = f.read()
      except FileNotFoundError:
          text = ""
      data = json.loads(text) if text.strip() else {}
      if data.get("model") in (None, "", "Gemini 4 Neon"):
          data["model"] = "Gemini 4 Neon (High)"
          os.makedirs(os.path.dirname(path), exist_ok=True)
          tmp = path + ".tmp"
          fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
          with os.fdopen(fd, "w") as f:
              json.dump(data, f, indent=2)
              f.write("\n")
          os.replace(tmp, path)
      EOF
      fi
    '';
  };
}
