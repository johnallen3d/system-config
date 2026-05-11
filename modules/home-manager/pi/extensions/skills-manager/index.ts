import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { parseSkillBlock } from "@earendil-works/pi-coding-agent";
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
      `skills: ${expandedSkills.size}/${n} expanded`);
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
            expandedSkills.set(parsed.name, { via: `skill-invocation @ turn ${turn + 1}` });
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
      expandedSkills.set(key, { via: `read @ turn ${currentTurn + 1}` });
    }
  });

  function buildReport(ctx: any): { text: string; skills: any[] } {
    const discovered = parseDiscovered(ctx.getSystemPrompt())
      .sort((a, b) => a.name.localeCompare(b.name));
    const lines: string[] = [
      `Skills (${expandedSkills.size} expanded / ${discovered.length} discovered)`,
      "",
    ];
    const skillRows: any[] = [];

    for (const s of discovered) {
      const info  = expandedSkills.get(s.name);
      const check = info ? "\u2713" : " ";
      const via   = info ? `via: ${info.via}` : "discovered only";
      lines.push(`${check} ${s.name.padEnd(28)} ${via}`);
      skillRows.push({ name: s.name, expanded: !!info, via: info?.via ?? null, location: s.location });
    }

    for (const [key, info] of expandedSkills) {
      if (!discovered.some(s => s.name === key)) {
        lines.push(`\u2713 ${key.padEnd(28)} via: ${info.via}`);
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
