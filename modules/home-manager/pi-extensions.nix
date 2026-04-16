# Consolidated pi agent extensions and themes.
#
# Code extensions (JS/TS) → ~/.pi/agent/extensions/<name>/
# Theme-only packages    → ~/.pi/agent/themes/<theme-name>.json
#
# To add a new extension or theme:
#   1. Add entry to `extensions` or `themes` below
#   2. Drop its package-lock.json into packages/<name>-package-lock.json
#   3. Use a dummy npmDepsHash, run `nix-rebuild --switch-only`, grab real hash from error
#
{pkgs, ...}: let
  mkPiExtension = {
    pname,
    version,
    url ? "https://registry.npmjs.org/${pname}/-/${pkgs.lib.lists.last (pkgs.lib.splitString "/" pname)}-${version}.tgz",
    hash,
    npmDepsHash,
    lockfile,
    description ? "",
    homepage ? "",
    forceEmptyCache ? false,
    npmInstallFlags ? [],
    extraInstallPhase ? "",
    nativeBuildInputs ? [],
  }:
    pkgs.buildNpmPackage {
      inherit pname version npmDepsHash forceEmptyCache npmInstallFlags nativeBuildInputs;

      src = pkgs.fetchurl {inherit url hash;};

      sourceRoot = "package";
      dontNpmBuild = true;

      postPatch = ''
        cp ${lockfile} package-lock.json
      '';

      installPhase = ''
        runHook preInstall
        mkdir -p $out
        cp -r ./* $out/
        ${extraInstallPhase}
        runHook postInstall
      '';

      meta = with pkgs.lib; {
        inherit description homepage;
        license = licenses.mit;
      };
    };

  # Local extensions — inline TS source, no npm packaging needed.
  # Shared (personal): loaded in ~/.config/pi/extensions/
  localExtensions = {
    auto-caveman = pkgs.writeTextDir "index.ts" ''
      import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
      import { readFileSync } from "node:fs";
      import { homedir } from "node:os";
      import { join } from "node:path";

      function loadSkill(relPath: string): string {
        try {
          return readFileSync(join(homedir(), relPath), "utf8");
        } catch {
          return "";
        }
      }

      export default function (pi: ExtensionAPI) {
        pi.on("session_start", async (_event, ctx) => {
          const isWork = process.env["PI_CODING_AGENT_DIR"]?.endsWith("pi-work");
          if (!isWork) {
            ctx.ui.notify("🦴 caveman ultra active", "info");
          }
        });

        pi.on("before_agent_start", async (event) => {
          const skills = [
            ".agents/skills/caveman/SKILL.md",
            ".agents/skills/caveman-commit/SKILL.md",
            ".agents/skills/caveman-review/SKILL.md",
          ]
            .map(loadSkill)
            .filter(Boolean)
            .join("\n\n");

          // Patch caveman to ultra intensity
          const patched = skills.replace(
            /Default: \*\*full\*\*/,
            "Default: **ultra**"
          );

          return {
            systemPrompt: event.systemPrompt + "\n\n" + patched,
          };
        });
      }
    '';
  };

  # Work-only local extensions — loaded exclusively in ~/.config/pi-work/extensions/
  localWorkExtensions = {
    auto-work = pkgs.writeTextDir "index.ts" ''
      import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
      import { readFileSync } from "node:fs";
      import { homedir } from "node:os";
      import { join } from "node:path";

      export default function (pi: ExtensionAPI) {
        pi.on("session_start", async (_event, ctx) => {
          ctx.ui.notify("🦴💼 caveman ultra + work mode active", "info");
        });

        pi.on("before_agent_start", async (event) => {
          const skillPaths = [
            "dev/src/amfaro/skills/notify-on-completion/SKILL.md",
            "dev/src/amfaro/skills/gh-pr-ops/SKILL.md",
          ];
          const skills = skillPaths
            .map((p) => { try { return readFileSync(join(homedir(), p), "utf8"); } catch { return ""; } })
            .filter(Boolean)
            .join("\n\n");
          if (!skills) return;
          return {
            systemPrompt: event.systemPrompt + "\n\n" + skills,
          };
        });
      }
    '';
  };

  # npm-packaged extensions — loaded by pi from ~/.config/pi/extensions/
  extensions = {
    pi-mcp-adapter = mkPiExtension {
      pname = "pi-mcp-adapter";
      version = "2.2.2";
      hash = "sha512-aT7eKpjYP558ZiYrlmCABNTuzUiw8eRY10rpgrygsZWfdfo5eC51Jc+NuB0V+lZ+5uGHwPJcZLPadmeO1zXQSA==";
      npmDepsHash = "sha256-qMI9QnIYXvq8JMVrR8zcGNhO2caSSvo1Pq71PR9IjGM=";
      lockfile = ./packages/pi-mcp-adapter-package-lock.json;
      description = "MCP adapter extension for pi coding agent";
      homepage = "https://github.com/nicobailon/pi-mcp-adapter";
    };

    pi-tasks = mkPiExtension {
      pname = "@tintinweb/pi-tasks";
      version = "0.4.2";
      hash = "sha256-XXZCs/7yJfSz0aY5DeW87n8beJwg9tEmm+cJa0y4YVQ=";
      npmDepsHash = "sha256-1tmviUr/xYFebp5kV+59HiGlZIdfLqpkqqHSYUiZq8A=";
      lockfile = ./packages/pi-tasks-package-lock.json;
      description = "Task tracking and coordination for pi coding agent";
      homepage = "https://github.com/tintinweb/pi-tasks";
    };

    pi-markdown-preview = mkPiExtension {
      pname = "pi-markdown-preview";
      version = "0.9.6";
      hash = "sha256-5C/EjaIzZMIpx5u1x1NO/Z4gZqmsda/TGNpnnHe5mP4=";
      npmDepsHash = "sha256-/hHvhFRkhfW8FqTGVbD+u9s2G+E/ZHo93Bd1m5XrCJw=";
      lockfile = ./packages/pi-markdown-preview-package-lock.json;
      description = "Markdown preview renderer for pi coding agent";
      homepage = "https://github.com/thesved/pi-markdown-preview";
    };

    memex = mkPiExtension {
      pname = "@touchskyer/memex";
      version = "0.1.28";
      hash = "sha256-NdIeDfqjiJvANZrYWICaEvGv6fOOdHHwTItNg2RjT/I=";
      npmDepsHash = "sha256-RhoLTqp2cCO6u6UZ36H7mjRMkq8necuzI2+Rc/nvR6s=";
      lockfile = ./packages/memex-package-lock.json;
      description = "Zettelkasten-based agent memory system with bidirectional links";
      homepage = "https://github.com/iamtouchskyer/memex";
      npmInstallFlags = [ "--ignore-scripts" ];
    };

    pi-lens = mkPiExtension {
      pname = "pi-lens";
      version = "3.8.25";
      hash = "sha256-sSb74h5HJ5+KSUVs11NzgVYqi/fDPagIMsviBCziEt0=";
      npmDepsHash = "sha256-Yw9YwSR9flIKGceV9fs9N5HFRoDHPll35YmxXL0PakE=";
      lockfile = ./packages/pi-lens-package-lock.json;
      description = "Real-time code feedback for pi — LSP, linters, formatters, type-checking";
      homepage = "https://github.com/apmantza/pi-lens";
      # postinstall downloads tree-sitter WASM grammars from the network, which
      # fails in the Nix sandbox. Skip it and copy the grammars from a prefetched
      # tree-sitter-wasms tarball instead.
      npmInstallFlags = [ "--ignore-scripts" ];
      nativeBuildInputs = [ pkgs.gnutar ];
      extraInstallPhase = let
        treeSitterWasms = pkgs.fetchurl {
          url = "https://registry.npmjs.org/tree-sitter-wasms/-/tree-sitter-wasms-0.1.13.tgz";
          hash = "sha256-ZqVKm7smhej2G0WM7xR021TnKXnuLeFo6LYCtWI1DdA=";
        };
        grammars = [
          "tree-sitter-typescript.wasm"
          "tree-sitter-tsx.wasm"
          "tree-sitter-javascript.wasm"
          "tree-sitter-python.wasm"
          "tree-sitter-rust.wasm"
          "tree-sitter-go.wasm"
          "tree-sitter-java.wasm"
          "tree-sitter-c.wasm"
          "tree-sitter-cpp.wasm"
          "tree-sitter-ruby.wasm"
        ];
      in ''
        grammarsDest=$out/node_modules/web-tree-sitter/grammars
        mkdir -p "$grammarsDest"
        tmpdir=$(mktemp -d)
        tar -xzf ${treeSitterWasms} -C "$tmpdir"
        ${pkgs.lib.concatMapStringsSep "\n" (f: ''cp "$tmpdir/package/out/${f}" "$grammarsDest/"'') grammars}
        rm -rf "$tmpdir"
      '';
    };

    pi-answer = mkPiExtension {
      pname = "pi-answer";
      version = "0.1.2";
      hash = "sha256-BEQJL+aO8W+CZcuSQsGkmESBe9M5q3+9Hnl/x5Ryts4=";
      npmDepsHash = "sha256-kgaWStajCnd2bOiv1T5dlPtntywKMqWqdFW6gpZNACc=";
      lockfile = ./packages/pi-answer-package-lock.json;
      description = "Interactive Q&A extraction for pi — run /answer to extract and answer questions";
      homepage = "https://www.npmjs.com/package/pi-answer";
    };

    pi-web-access = mkPiExtension {
      pname = "pi-web-access";
      version = "0.10.6";
      hash = "sha256-93u8a41wgsyK1v2XUuxkycwjbFiP4ToOjBUqPmO4wtk=";
      npmDepsHash = "sha256-zwH9ba5M6wRtyTdpi/7To/ZzkQfNvgO8CxdpGCeB8Vo=";
      lockfile = ./packages/pi-web-access-package-lock.json;
      description = "Web access extension for pi coding agent";
      homepage = "https://github.com/mariozechner/pi-web-access";
    };
  };
  # Theme-only packages — theme JSON linked directly to ~/.pi/agent/themes/
  # so pi auto-discovers them without needing a settings.json entry.
  # Each entry maps "theme-name" -> { pkg, file } where file is the JSON filename.
  themes = {
    tokyo-night-storm = {
      pkg = mkPiExtension {
        pname = "pi-tokyo-night-storm";
        version = "1.0.0";
        hash = "sha256-CwRmlhMlIeEJN8D0tQ+S6TGVbPBBJEWZs5jUxfE6QPY=";
        npmDepsHash = "sha256-Aeyt2zVmx1UpOVZ8T8dRWRPf9uu+Pau8fKkAxWf6tDQ=";
        lockfile = ./packages/pi-tokyo-night-storm-package-lock.json;
        description = "Tokyo Night Storm theme for pi coding agent";
        homepage = "https://github.com/sanathks/pi-tokyo-night-storm";
        forceEmptyCache = true;
      };
      file = "tokyo-night-storm.json";
    };
  };
in {
  home.file =
    # Shared extensions — personal context
    (pkgs.lib.mapAttrs'
      (name: pkg:
        pkgs.lib.nameValuePair ".config/pi/extensions/${name}" {source = pkg;})
      (extensions // localExtensions))
    # Shared extensions — also present in work context
    // (pkgs.lib.mapAttrs'
      (name: pkg:
        pkgs.lib.nameValuePair ".config/pi-work/extensions/${name}" {source = pkg;})
      (extensions // localExtensions))
    # Work-only extensions
    // (pkgs.lib.mapAttrs'
      (name: pkg:
        pkgs.lib.nameValuePair ".config/pi-work/extensions/${name}" {source = pkg;})
      localWorkExtensions)
    # Themes — personal context (pi-work symlinks to this dir, see pi-settings.nix)
    // (pkgs.lib.mapAttrs'
      (name: theme:
        pkgs.lib.nameValuePair ".config/pi/themes/${name}.json" {source = "${theme.pkg}/themes/${theme.file}";})
      themes);
}
