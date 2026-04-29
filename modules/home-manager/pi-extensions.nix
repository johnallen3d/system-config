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
    extraPostPatch ? "",
    nativeBuildInputs ? [],
  }:
    pkgs.buildNpmPackage {
      inherit pname version npmDepsHash forceEmptyCache npmInstallFlags nativeBuildInputs;

      src = pkgs.fetchurl {inherit url hash;};

      sourceRoot = "package";
      dontNpmBuild = true;

      postPatch = ''
        cp ${lockfile} package-lock.json
        ${extraPostPatch}
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
    # Unified skill injection + tracking for personal and work sessions.
    # Replaces auto-caveman + auto-work + pi-loaded-skills.
    skills-manager = pkgs.writeTextDir "index.ts" ''
      import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
      import { parseSkillBlock } from "@mariozechner/pi-coding-agent";
      import { readFileSync } from "node:fs";
      import { homedir } from "node:os";
      import { join } from "node:path";
      import { Type } from "@sinclair/typebox";

      const isWork = () => process.env["PI_CODING_AGENT_DIR"]?.endsWith("pi-work") ?? false;

      // Skills injected every turn, keyed by session context
      const SHARED_SKILL_PATHS = [
        ".agents/skills/caveman/SKILL.md",
        ".agents/skills/caveman-commit/SKILL.md",
        ".agents/skills/caveman-review/SKILL.md",
      ];
      const WORK_SKILL_PATHS = [
        "dev/src/amfaro/skills/notify-on-completion/SKILL.md",
        "dev/src/amfaro/skills/gh-pr-ops/SKILL.md",
      ];

      function activeSkillPaths(): string[] {
        return isWork()
          ? [...SHARED_SKILL_PATHS, ...WORK_SKILL_PATHS]
          : SHARED_SKILL_PATHS;
      }

      interface DiscoveredSkill { name: string; location: string; description: string; }
      interface ExpandedInfo   { via: string; }

      function loadSkill(relPath: string): string {
        try { return readFileSync(join(homedir(), relPath), "utf8"); }
        catch { return ""; }
      }

      function skillNameFromContent(content: string): string | null {
        const m = content.match(/^name:\s*(\S+)/m);
        return m ? m[1] : null;
      }

      function parseDiscovered(prompt: string): DiscoveredSkill[] {
        const block = prompt.match(/<available_skills>([\s\S]*?)<\/available_skills>/);
        if (!block) return [];
        const skills: DiscoveredSkill[] = [];
        const re = /<skill>[\s\S]*?<name>([^<]+)<\/name>[\s\S]*?<description>([^<]*)<\/description>[\s\S]*?<location>([^<]+)<\/location>[\s\S]*?<\/skill>/g;
        let m: RegExpExecArray | null;
        while ((m = re.exec(block[1])) !== null) {
          skills.push({ name: m[1].trim(), description: m[2].trim(), location: m[3].trim() });
        }
        return skills;
      }

      export default function (pi: ExtensionAPI) {
        const expandedSkills = new Map<string, ExpandedInfo>();
        let currentTurn = 0;

        pi.on("turn_start", (event) => { currentTurn = event.turnIndex; });

        function updateStatus(ctx: any) {
          const n = parseDiscovered(ctx.getSystemPrompt()).length;
          ctx.ui.setStatus("pi-loaded-skills",
            `skills: ''${expandedSkills.size}/''${n} expanded`);
        }

        function scanBranch(ctx: any) {
          let turn = 0;
          for (const entry of ctx.sessionManager.getBranch()) {
            if (entry.type !== "message") continue;
            const msg = (entry as any).message;
            if (msg?.role === "user") {
              const text = typeof msg.content === "string"
                ? msg.content
                : (msg.content as any[])?.find((c: any) => c.type === "text")?.text;
              if (text) {
                const parsed = parseSkillBlock(text);
                if (parsed && !expandedSkills.has(parsed.name)) {
                  expandedSkills.set(parsed.name, { via: `skill-invocation @ turn ''${turn + 1}` });
                }
              }
            }
            turn++;
          }
        }

        pi.on("session_start", (_event, ctx) => {
          // Mark all auto-injected skills expanded immediately — we know exactly what we load
          for (const relPath of activeSkillPaths()) {
            const content = loadSkill(relPath);
            if (!content) continue;
            const name = skillNameFromContent(content);
            if (name && !expandedSkills.has(name)) {
              expandedSkills.set(name, { via: "system-prompt" });
            }
          }

          scanBranch(ctx);
          updateStatus(ctx);

          if (isWork()) {
            ctx.ui.notify("🦴💼 caveman ultra + work skills active", "info");
          } else {
            ctx.ui.notify("🦴 caveman ultra active", "info");
          }
        });

        pi.on("before_agent_start", async (event) => {
          const skills = activeSkillPaths().map(loadSkill).filter(Boolean).join("\n\n");
          const patched = skills.replace(/Default: \*\*full\*\*/, "Default: **ultra**");
          return { systemPrompt: event.systemPrompt + "\n\n" + patched };
        });

        pi.on("turn_end", (_event, ctx) => {
          scanBranch(ctx);
          updateStatus(ctx);
        });

        pi.on("tool_result", (event, ctx) => {
          if (event.toolName !== "read") return;
          const path: string = (event.input as any)["path"] ?? "";
          if (!path.endsWith("SKILL.md") && !(path.includes("/skills/") && path.endsWith(".md"))) return;
          const discovered = parseDiscovered(ctx.getSystemPrompt());
          const match = discovered.find(s => s.location === path);
          const key = match?.name ?? path;
          if (!expandedSkills.has(key)) {
            expandedSkills.set(key, { via: `read @ turn ''${currentTurn + 1}` });
          }
        });

        function buildReport(ctx: any): { text: string; skills: any[] } {
          const discovered = parseDiscovered(ctx.getSystemPrompt())
            .sort((a, b) => a.name.localeCompare(b.name));
          const lines: string[] = [
            `Skills (''${expandedSkills.size} expanded / ''${discovered.length} discovered)`,
            "",
          ];
          const skillRows: any[] = [];

          for (const s of discovered) {
            const info  = expandedSkills.get(s.name);
            const check = info ? "\u2713" : " ";
            const via   = info ? `via: ''${info.via}` : "discovered only";
            lines.push(`''${check} ''${s.name.padEnd(28)} ''${via}`);
            skillRows.push({ name: s.name, expanded: !!info, via: info?.via ?? null, location: s.location });
          }

          for (const [key, info] of expandedSkills) {
            if (!discovered.some(s => s.name === key)) {
              lines.push(`\u2713 ''${key.padEnd(28)} via: ''${info.via}`);
              skillRows.push({ name: key, expanded: true, via: info.via });
            }
          }

          return { text: lines.join("\n"), skills: skillRows };
        }

        pi.registerCommand("skills-loaded", {
          description: "Show which skills are loaded (expanded vs discovered)",
          handler: async (_args: string, ctx: any) => {
            pi.sendMessage({
              customType: "skills-loaded-report",
              content: buildReport(ctx).text,
              display: true,
            });
          },
        });

        pi.registerTool({
          name: "loaded_skills",
          label: "Loaded Skills",
          description:
            "Report which pi skills are currently expanded in context versus merely discovered. " +
            "Returns structured list with expansion status, via (how loaded), and location.",
          parameters: Type.Object({}),
          execute: async (_id: string, _p: any, _sig: any, _upd: any, ctx: any) => {
            const { text, skills } = buildReport(ctx);
            return {
              content: [{ type: "text" as const, text }],
              details: {
                expandedCount: skills.filter((s: any) => s.expanded).length,
                discoveredCount: skills.length,
                skills,
              },
            };
          },
        });
      }
    '';

    # Custom footer with provider-specific usage, model, and context usage.
    usage-footer = pkgs.writeTextDir "index.ts" ''
      import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
      import { AuthStorage } from "@mariozechner/pi-coding-agent";
      import { truncateToWidth, visibleWidth } from "@mariozechner/pi-tui";

      type WindowUsage = {
        label: string;
        usedPercent?: number;
        resetAt?: number;
        windowSeconds?: number;
      };
      type CodexUsage = { plan?: string; windows: WindowUsage[]; credits?: string; error?: string; fetchedAt?: number };
      type CopilotUsage = { plan?: string; text?: string; error?: string; fetchedAt?: number };

      const authStorage = AuthStorage.create();
      const POLL_MS = 60_000;
      let codexUsage: CodexUsage | undefined;
      let copilotUsage: CopilotUsage | undefined;
      let lastCodexFetch = 0;
      let lastCopilotFetch = 0;
      let requestRender: (() => void) | undefined;

      function formatTokens(count: number): string {
        if (!Number.isFinite(count) || count < 0) return "?";
        if (count < 1000) return String(Math.round(count));
        if (count < 10000) return (count / 1000).toFixed(1) + "k";
        if (count < 1000000) return Math.round(count / 1000) + "k";
        if (count < 10000000) return (count / 1000000).toFixed(1) + "M";
        return Math.round(count / 1000000) + "M";
      }

      function fmtPercent(value: number | undefined): string {
        return typeof value === "number" && Number.isFinite(value) ? Math.round(value) + "%" : "?%";
      }

      function normalizeEpochMs(value: number | undefined): number | undefined {
        if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return undefined;
        return value > 1_000_000_000_000 ? value : value * 1000;
      }

      function formatResetAt(resetAt: number | undefined, windowSeconds: number | undefined): string | undefined {
        const epochMs = normalizeEpochMs(resetAt);
        if (!epochMs) return undefined;
        const now = new Date();
        const date = new Date(epochMs);
        const sameDay = now.toDateString() === date.toDateString();
        return new Intl.DateTimeFormat(undefined, {
          weekday: windowSeconds && windowSeconds > 86400 && !sameDay ? "short" : undefined,
          hour: "numeric",
          minute: "2-digit",
        }).format(date);
      }

      function windowLabel(seconds: number | undefined, fallback: string): string {
        if (seconds === 18000) return "5h";
        if (seconds === 604800) return "7d";
        if (seconds && seconds % 3600 === 0 && seconds < 86400) return (seconds / 3600) + "h";
        if (seconds && seconds % 86400 === 0) return (seconds / 86400) + "d";
        return fallback;
      }

      function codexWindow(raw: any, fallback: string): WindowUsage | undefined {
        if (!raw || typeof raw !== "object") return undefined;
        const limitWindowSeconds = typeof raw.limit_window_seconds === "number" ? raw.limit_window_seconds : undefined;
        return {
          label: windowLabel(limitWindowSeconds, fallback),
          usedPercent: typeof raw.used_percent === "number" ? raw.used_percent : undefined,
          resetAt: typeof raw.reset_at === "number" ? raw.reset_at : undefined,
          windowSeconds: limitWindowSeconds,
        };
      }

      async function fetchCodexUsage(force = false): Promise<void> {
        const now = Date.now();
        if (!force && now - lastCodexFetch < POLL_MS) return;
        lastCodexFetch = now;
        try {
          authStorage.reload();
          const access = await authStorage.getApiKey("openai-codex");
          const credential = authStorage.getAll()["openai-codex"] as any;
          if (!access) throw new Error("not logged in");
          const headers: Record<string, string> = {
            "Authorization": "Bearer " + access,
            "Accept": "application/json",
          };
          if (credential?.accountId) headers["ChatGPT-Account-Id"] = String(credential.accountId);
          const res = await fetch("https://chatgpt.com/backend-api/wham/usage", { headers });
          if (!res.ok) throw new Error("HTTP " + res.status);
          const data = await res.json() as any;
          const windows = [
            codexWindow(data?.rate_limit?.primary_window, "5h"),
            codexWindow(data?.rate_limit?.secondary_window, "7d"),
          ].filter(Boolean) as WindowUsage[];
          let credits: string | undefined;
          if (data?.credits?.has_credits) {
            credits = data.credits.unlimited ? "unlimited credits" : "$" + Number(data.credits.balance ?? 0).toFixed(2) + " credits";
          }
          codexUsage = { plan: data?.plan_type, windows, credits, fetchedAt: now };
        } catch (err) {
          codexUsage = { windows: [], error: err instanceof Error ? err.message : String(err), fetchedAt: now };
        } finally {
          requestRender?.();
        }
      }

      async function fetchCopilotUsage(force = false): Promise<void> {
        const now = Date.now();
        if (!force && now - lastCopilotFetch < POLL_MS) return;
        lastCopilotFetch = now;
        try {
          authStorage.reload();
          const credential = authStorage.getAll()["github-copilot"] as any;
          const token = credential?.refresh ?? process.env["GH_TOKEN"] ?? process.env["GITHUB_TOKEN"];
          if (!token) throw new Error("not logged in");
          const res = await fetch("https://api.github.com/copilot_internal/user", {
            headers: {
              "Authorization": "token " + token,
              "Accept": "application/json",
              "Editor-Version": "vscode/1.96.2",
              "Editor-Plugin-Version": "copilot-chat/0.26.7",
              "User-Agent": "GitHubCopilotChat/0.26.7",
              "X-GitHub-Api-Version": "2025-04-01",
            },
          });
          if (!res.ok) throw new Error("HTTP " + res.status);
          const data = await res.json() as any;
          const premium = data?.quota_snapshots?.premium_interactions;
          let text: string | undefined;
          if (premium && typeof premium.entitlement === "number" && typeof premium.remaining === "number") {
            const used = Math.max(0, premium.entitlement - premium.remaining);
            const percent = premium.entitlement > 0 ? Math.round((used / premium.entitlement) * 100) : 0;
            text = "credits " + used + "/" + premium.entitlement + " (" + percent + "%)";
          } else if (data?.limited_user_quotas && data?.monthly_quotas) {
            const chat = data.limited_user_quotas.chat;
            const total = data.monthly_quotas.chat;
            if (typeof chat === "number" && typeof total === "number") {
              text = "chat " + (total - chat) + "/" + total;
            }
          }
          copilotUsage = { plan: data?.copilot_plan ?? data?.access_type_sku, text: text ?? "credits ?", fetchedAt: now };
        } catch (err) {
          copilotUsage = { error: err instanceof Error ? err.message : String(err), fetchedAt: now };
        } finally {
          requestRender?.();
        }
      }

      function sessionCost(ctx: any): number {
        let total = 0;
        for (const entry of ctx.sessionManager.getEntries()) {
          if (entry.type === "message" && entry.message?.role === "assistant") {
            total += entry.message.usage?.cost?.total ?? 0;
          }
        }
        return total;
      }

      function usageText(ctx: any): string {
        const provider = ctx.model?.provider;
        if (provider === "openai-codex") {
          void fetchCodexUsage();
          if (codexUsage?.error) return "usage: codex " + codexUsage.error;
          const windows = codexUsage?.windows?.map(w => {
            const reset = formatResetAt(w.resetAt, w.windowSeconds);
            return w.label + " " + fmtPercent(w.usedPercent) + (reset ? "→" + reset : "");
          }).join(" / ");
          const plan = codexUsage?.plan ? codexUsage.plan + " " : "";
          const credits = codexUsage?.credits ? " • " + codexUsage.credits : "";
          return "usage: codex " + plan + (windows || "?") + credits;
        }
        if (provider === "github-copilot") {
          void fetchCopilotUsage();
          if (copilotUsage?.error) return "usage: copilot " + copilotUsage.error;
          const plan = copilotUsage?.plan ? copilotUsage.plan + " " : "";
          return "usage: copilot " + plan + (copilotUsage?.text ?? "credits ?");
        }
        return "usage: $" + sessionCost(ctx).toFixed(3) + " session";
      }

      function contextText(ctx: any): { text: string; percent: number | undefined } {
        const usage = ctx.getContextUsage?.();
        const tokens = usage?.tokens;
        const limit = usage?.contextWindow ?? ctx.model?.contextWindow;
        const percent = typeof usage?.percent === "number" ? usage.percent :
          (typeof tokens === "number" && typeof limit === "number" && limit > 0 ? (tokens / limit) * 100 : undefined);
        return {
          text: "ctx " + formatTokens(tokens ?? 0) + "/" + formatTokens(limit ?? 0) + " " + fmtPercent(percent),
          percent,
        };
      }

      function modelText(ctx: any): string {
        const provider = ctx.model?.provider ?? "no-provider";
        const model = ctx.model?.id ?? "no-model";
        return provider + "/" + model;
      }

      function installFooter(ctx: any) {
        ctx.ui.setFooter((tui: any, theme: any, footerData: any) => {
          requestRender = () => tui.requestRender();
          const unsub = footerData.onBranchChange(() => tui.requestRender());
          const interval = setInterval(() => tui.requestRender(), 30_000);
          return {
            dispose() {
              clearInterval(interval);
              unsub();
              if (requestRender) requestRender = undefined;
            },
            invalidate() {},
            render(width: number): string[] {
              const ctxInfo = contextText(ctx);
              const context = ctxInfo.percent !== undefined && ctxInfo.percent > 90
                ? theme.fg("error", ctxInfo.text)
                : ctxInfo.percent !== undefined && ctxInfo.percent > 70
                  ? theme.fg("warning", ctxInfo.text)
                  : ctxInfo.text;
              const left = theme.fg("dim", usageText(ctx)) + " " + theme.fg("dim", "|") + " " + context;
              const right = theme.fg("dim", modelText(ctx));
              const pad = " ".repeat(Math.max(1, width - visibleWidth(left) - visibleWidth(right)));
              const line = truncateToWidth(left + pad + right, width, theme.fg("dim", "..."));

              const statuses = Array.from(footerData.getExtensionStatuses().entries())
                .sort(([a], [b]) => String(a).localeCompare(String(b)))
                .map(([, text]) => String(text).replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim())
                .filter(Boolean)
                .join(" ");
              return statuses ? [line, truncateToWidth(statuses, width, theme.fg("dim", "..."))] : [line];
            },
          };
        });
      }

      export default function (pi: ExtensionAPI) {
        pi.on("session_start", (_event, ctx) => {
          installFooter(ctx);
          if (ctx.model?.provider === "openai-codex") void fetchCodexUsage(true);
          if (ctx.model?.provider === "github-copilot") void fetchCopilotUsage(true);
        });
        pi.on("model_select", (event, ctx) => {
          if (event.model?.provider === "openai-codex") void fetchCodexUsage(true);
          if (event.model?.provider === "github-copilot") void fetchCopilotUsage(true);
          requestRender?.();
        });
        pi.on("agent_end", (_event, ctx) => {
          if (ctx.model?.provider === "openai-codex") void fetchCodexUsage(true);
          if (ctx.model?.provider === "github-copilot") void fetchCopilotUsage(true);
          requestRender?.();
        });
      }
    '';

  };

  # Work-only extensions slot kept for future use; skills-manager handles work injection.
  localWorkExtensions = {};

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
      extraPostPatch = ''
        substituteInPlace clients/language-policy.ts \
          --replace-fail 'defaults: ["sqlfluff"],' 'defaults: [],' \
          --replace-fail 'runnerIds: ["sqlfluff"],' 'runnerIds: [],'
        substituteInPlace clients/dispatch/plan.ts \
          --replace-fail 'writeGroups: [primary("sql")],' 'writeGroups: [],'
        substituteInPlace clients/formatters.ts \
          --replace-fail $'\tsqlfluffFormatter,\n' ""
        substituteInPlace clients/dispatch/runners/index.ts \
          --replace-fail 'import sqlfluffRunner from "./sqlfluff.js";' '// sqlfluff disabled locally' \
          --replace-fail $'\tregistry.register(sqlfluffRunner); // SQL lint (priority 24)\n' ""
      '';
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
