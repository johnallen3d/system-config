import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import type {
  ExtensionAPI,
  ExtensionCommandContext,
  SessionEntry,
  Skill,
} from "@earendil-works/pi-coding-agent";

type ToolInfo = ReturnType<ExtensionAPI["getAllTools"]>[number];

type ActiveTool = {
  name: string;
  estimatedTokens: number | null;
  tool?: ToolInfo;
};

type CachedServer = {
  name: string;
  toolCount: number;
};

type ContextComponents = {
  systemPrompt: number;
  skillMetadata: number;
  loadedSkills: number;
  toolSchemas: number;
  messages: number;
  toolCalls: number;
  toolResults: number;
};

type SkillMetadataEstimate = {
  prompt: string;
  estimatedTokens: number;
  overheadTokens: number;
  skills: Array<{ name: string; estimatedTokens: number; source: string }>;
};

const numberFormat = new Intl.NumberFormat("en-US");
const estimatedImageChars = 4_800;

function estimateChars(chars: number): number {
  return Math.ceil(chars / 4);
}

function formatSkillSource(skill: Skill): string {
  if (skill.sourceInfo.origin === "package") return skill.sourceInfo.source;
  return `${skill.sourceInfo.scope} local`;
}

function estimateContentTokens(content: unknown): number {
  if (typeof content === "string") return estimateChars(content.length);
  if (!Array.isArray(content)) return 0;

  const chars = content.reduce((total, block) => {
    if (!block || typeof block !== "object") return total;
    const item = block as { type?: string; text?: string; data?: string };
    if (item.type === "text") return total + (item.text?.length ?? 0);
    if (item.type === "image") return total + estimatedImageChars;
    return total;
  }, 0);
  return estimateChars(chars);
}

export function estimateToolTokens(tool: Pick<ToolInfo, "name" | "description" | "parameters">): number {
  const schemaLength = JSON.stringify(tool.parameters ?? {}).length;
  return estimateChars(tool.name.length + (tool.description?.length ?? 0) + schemaLength) + 10;
}

export function selectActiveTools(activeNames: string[], allTools: ToolInfo[]): ActiveTool[] {
  const toolsByName = new Map(allTools.map((tool) => [tool.name, tool]));
  return activeNames.map((name) => {
    const tool = toolsByName.get(name);
    return {
      name,
      estimatedTokens: tool ? estimateToolTokens(tool) : null,
      ...(tool ? { tool } : {}),
    };
  });
}

export function estimateSkillMetadata(systemPrompt: string, skills: Skill[]): SkillMetadataEstimate {
  const listStart = systemPrompt.lastIndexOf("<available_skills>");
  const listEnd = systemPrompt.indexOf("</available_skills>", listStart);
  if (listStart < 0 || listEnd < 0) {
    return { prompt: "", estimatedTokens: 0, overheadTokens: 0, skills: [] };
  }

  const introStart = systemPrompt.lastIndexOf("\n\nThe following skills provide specialized instructions", listStart);
  const prompt = systemPrompt.slice(introStart >= 0 ? introStart : listStart, listEnd + "</available_skills>".length);
  const visibleSkills = skills.filter((skill) => !skill.disableModelInvocation);
  const blocks = prompt.match(/  <skill>\n[\s\S]*?\n  <\/skill>/g) ?? [];
  const skillCosts = visibleSkills.map((skill, index) => ({
    name: skill.name,
    estimatedTokens: estimateChars(blocks[index]?.length ?? 0),
    source: formatSkillSource(skill),
  }));
  const blockChars = blocks.reduce((total, block) => total + block.length, 0);

  return {
    prompt,
    estimatedTokens: estimateChars(prompt.length),
    overheadTokens: estimateChars(prompt.length - blockChars),
    skills: skillCosts,
  };
}

export function estimateContextComponents(
  systemPrompt: string,
  entries: SessionEntry[],
  toolSchemas: number,
  skillMetadata = 0,
): ContextComponents {
  const components: ContextComponents = {
    systemPrompt: estimateChars(systemPrompt.length),
    skillMetadata,
    loadedSkills: 0,
    toolSchemas,
    messages: 0,
    toolCalls: 0,
    toolResults: 0,
  };

  for (const entry of entries) {
    if (entry.type === "custom_message") {
      const tokens = estimateContentTokens(entry.content);
      if (entry.customType === "skill-loaded") components.loadedSkills += tokens;
      else components.messages += tokens;
      continue;
    }
    if (entry.type === "compaction" || entry.type === "branch_summary") {
      components.messages += estimateChars(entry.summary.length);
      continue;
    }
    if (entry.type !== "message") continue;

    const message = entry.message;
    if (message.role === "assistant") {
      let messageChars = 0;
      let toolCallChars = 0;
      for (const block of message.content ?? []) {
        if (block.type === "text") messageChars += block.text.length;
        else if (block.type === "thinking") messageChars += block.thinking.length;
        else if (block.type === "toolCall") toolCallChars += block.name.length + JSON.stringify(block.arguments).length;
      }
      components.messages += estimateChars(messageChars);
      components.toolCalls += estimateChars(toolCallChars);
    } else if (message.role === "toolResult") {
      components.toolResults += estimateContentTokens(message.content);
    } else if (message.role === "bashExecution") {
      components.toolCalls += estimateChars(message.command.length);
      components.toolResults += estimateChars(message.output.length);
    } else if (message.role === "custom") {
      const tokens = estimateContentTokens(message.content);
      if (message.customType === "skill-loaded") components.loadedSkills += tokens;
      else components.messages += tokens;
    } else if (message.role === "branchSummary" || message.role === "compactionSummary") {
      components.messages += estimateChars(message.summary.length);
    } else {
      components.messages += estimateContentTokens(message.content);
    }
  }

  return components;
}

function sumComponents(components: ContextComponents): number {
  return Object.values(components).reduce((sum, tokens) => sum + tokens, 0);
}

function formatEstimate(tokens: number | null): string {
  return tokens === null ? "unknown" : `~${numberFormat.format(tokens)} tokens`;
}

function formatComponent(tokens: number, total: number | null, derived = false): string {
  const estimate = derived ? numberFormat.format(tokens) : `~${numberFormat.format(tokens)}`;
  const percentage = total && total > 0 ? ` (${((tokens / total) * 100).toFixed(1)}%)` : "";
  return `${estimate} tokens${percentage}${derived ? " derived" : ""}`;
}

function formatContext(ctx: ExtensionCommandContext): string {
  const usage = ctx.getContextUsage();
  if (!usage) return "Current context: unavailable";

  const configuredLimit = process.env.CLAUDE_CODE_DISABLE_1M_CONTEXT === "1" ? 200_000 : usage.contextWindow;
  const limit = Math.min(usage.contextWindow, configuredLimit);
  const tokens = usage.tokens;
  const percent = tokens === null || tokens === 0 || limit <= 0 ? null : (tokens / limit) * 100;
  const used = tokens === null ? "unknown" : tokens === 0 ? "not yet measured" : numberFormat.format(tokens);
  const percentage = percent === null ? "" : ` (${percent.toFixed(1)}%)`;
  return `Current context: ${used} / ${numberFormat.format(limit)} tokens${percentage}`;
}

function isMcpAdapterTool(tool: ToolInfo | undefined): boolean {
  if (!tool) return false;
  return `${tool.sourceInfo.source} ${tool.sourceInfo.path}`.toLowerCase().includes("pi-mcp-adapter");
}

async function readCachedServers(): Promise<CachedServer[] | null> {
  const agentDir = process.env.PI_CODING_AGENT_DIR;
  if (!agentDir) return null;

  try {
    const cache = JSON.parse(await readFile(`${agentDir}/mcp-cache.json`, "utf8")) as {
      servers?: Record<string, { tools?: unknown[] }>;
    };
    return Object.entries(cache.servers ?? {})
      .map(([name, server]) => ({ name, toolCount: server.tools?.length ?? 0 }))
      .sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    return [];
  }
}

function formatRows(rows: Array<[string, string]>): string[] {
  const width = Math.max(...rows.map(([label]) => label.length));
  return rows.map(([label, value]) => `  ${label.padEnd(width)}  ${value}`);
}

async function buildReport(pi: ExtensionAPI, ctx: ExtensionCommandContext): Promise<string> {
  const activeTools = selectActiveTools(pi.getActiveTools(), pi.getAllTools());
  const knownEstimates = activeTools.flatMap((tool) => tool.estimatedTokens === null ? [] : [tool.estimatedTokens]);
  const toolSchemaTotal = knownEstimates.reduce((sum, tokens) => sum + tokens, 0);
  const unknownCount = activeTools.length - knownEstimates.length;
  const toolRows = activeTools
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((tool): [string, string] => [tool.name, formatEstimate(tool.estimatedTokens)]);

  const usage = ctx.getContextUsage();
  const currentTotal = usage?.tokens && usage.tokens > 0 ? usage.tokens : null;
  const systemPrompt = ctx.getSystemPrompt();
  const promptOptions = ctx.getSystemPromptOptions();
  const skillMetadata = estimateSkillMetadata(systemPrompt, promptOptions.skills ?? []);
  const baseSystemPrompt = skillMetadata.prompt ? systemPrompt.replace(skillMetadata.prompt, "") : systemPrompt;
  const components = estimateContextComponents(
    baseSystemPrompt,
    ctx.sessionManager.buildContextEntries(),
    toolSchemaTotal,
    skillMetadata.estimatedTokens,
  );
  const componentTotal = sumComponents(components);
  const breakdownRows: Array<[string, string]> = [
    ["base system prompt", formatComponent(components.systemPrompt, currentTotal)],
    ["available skill metadata", formatComponent(components.skillMetadata, currentTotal)],
    ["loaded skill bodies", formatComponent(components.loadedSkills, currentTotal)],
    ["active tool schemas", formatComponent(components.toolSchemas, currentTotal)],
    ["conversation messages", formatComponent(components.messages, currentTotal)],
    ["tool calls", formatComponent(components.toolCalls, currentTotal)],
    ["tool results", formatComponent(components.toolResults, currentTotal)],
    ["estimated components", formatComponent(componentTotal, currentTotal)],
    ["residual / estimate delta", currentTotal === null ? "unknown" : formatComponent(currentTotal - componentTotal, currentTotal, true)],
  ];

  const adapterTools = activeTools.filter((tool) => isMcpAdapterTool(tool.tool));
  const proxy = adapterTools.find((tool) => tool.name === "mcp");
  const script = adapterTools.find((tool) => tool.name === "mcpScript");
  const direct = adapterTools.filter((tool) => tool.name !== "mcp" && tool.name !== "mcpScript");
  const directTokens = direct.reduce((sum, tool) => sum + (tool.estimatedTokens ?? 0), 0);
  const cachedServers = await readCachedServers();
  const mcpRows: Array<[string, string]> = [
    ["proxy gateway", proxy ? `active, ${formatEstimate(proxy.estimatedTokens)}` : "inactive"],
    ["script gateway", script ? `active, ${formatEstimate(script.estimatedTokens)}` : "inactive"],
    ["direct server tools", `${direct.length} active, ${formatEstimate(directTokens)}`],
  ];

  if (cachedServers === null) {
    mcpRows.push(["metadata cache", "unavailable: PI_CODING_AGENT_DIR not set"]);
  } else if (cachedServers.length === 0) {
    mcpRows.push(["metadata cache", "empty or unreadable"]);
  } else {
    mcpRows.push(...cachedServers.map((server): [string, string] => [server.name, `${server.toolCount} cached tools`]));
  }

  const skillRows: Array<[string, string, string]> = skillMetadata.skills
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((skill) => [skill.name, formatEstimate(skill.estimatedTokens), skill.source]);
  if (skillRows.length > 0) skillRows.push(["listing overhead", formatEstimate(skillMetadata.overheadTokens), ""]);
  const skillNameWidth = Math.max(...skillRows.map(([name]) => name.length));
  const skillCostWidth = Math.max(...skillRows.map(([, cost]) => cost.length));
  const formattedSkillRows = skillRows.map(
    ([name, cost, source]) => `  ${name.padEnd(skillNameWidth)}  ${cost.padEnd(skillCostWidth)}  ${source}`.trimEnd(),
  );

  const unknownSuffix = unknownCount ? `; ${unknownCount} unknown` : "";
  return [
    formatContext(ctx),
    "Scope: current context only; /session reports cumulative usage.",
    "Total uses Pi's provider-tokenizer count plus any trailing estimate; components use chars/4 estimates.",
    "",
    "Current-context breakdown:",
    ...formatRows(breakdownRows),
    "",
    skillRows.length > 0
      ? `Available skill metadata: ${skillMetadata.skills.length} skills, estimated prompt cost ${formatEstimate(skillMetadata.estimatedTokens)}`
      : "Available skill metadata: none in the effective system prompt",
    ...formattedSkillRows,
    "",
    `Active tools: ${activeTools.length}, estimated schema cost ${formatEstimate(toolSchemaTotal)}${unknownSuffix}`,
    ...formatRows(toolRows),
    "",
    "MCP (cache counts are not live connection state):",
    ...formatRows(mcpRows),
  ].join("\n");
}

export default function contextInspection(pi: ExtensionAPI) {
  pi.registerCommand("context", {
    description: "Show detailed current-context, active-tool, and MCP schema usage",
    handler: async (_args, ctx) => {
      ctx.ui.notify(await buildReport(pi, ctx), "info");
    },
  });
}

if (process.argv.includes("--self-test")) {
  const tools = [
    {
      name: "a",
      description: "bbb",
      parameters: {},
      promptGuidelines: [],
      sourceInfo: { path: "<builtin:a>", source: "builtin", scope: "temporary", origin: "top-level" },
    },
    {
      name: "inactive",
      description: "unused",
      parameters: {},
      promptGuidelines: [],
      sourceInfo: { path: "<builtin:inactive>", source: "builtin", scope: "temporary", origin: "top-level" },
    },
  ] as ToolInfo[];
  const entries = [
    {
      type: "custom_message",
      customType: "skill-loaded",
      content: "12345678",
      display: true,
    },
    {
      type: "message",
      message: {
        role: "assistant",
        content: [
          { type: "text", text: "1234" },
          { type: "toolCall", id: "1", name: "a", arguments: {} },
        ],
      },
    },
    {
      type: "message",
      message: { role: "toolResult", content: [{ type: "text", text: "1234" }] },
    },
  ] as SessionEntry[];

  const skills = [
    {
      name: "example",
      description: "Example skill",
      filePath: "/tmp/example/SKILL.md",
      disableModelInvocation: false,
      sourceInfo: {
        path: "/tmp/example/SKILL.md",
        source: "auto",
        scope: "project",
        origin: "top-level",
      },
    },
  ] as Skill[];
  const skillPrompt = `\n\nThe following skills provide specialized instructions for specific tasks.\n<available_skills>\n  <skill>\n    <name>example</name>\n    <description>Example skill</description>\n    <location>/tmp/example/SKILL.md</location>\n  </skill>\n</available_skills>`;
  const skillMetadata = estimateSkillMetadata(`base${skillPrompt}`, skills);

  assert.equal(estimateToolTokens(tools[0]), 12);
  assert.deepEqual(selectActiveTools(["a"], tools).map((tool) => tool.name), ["a"]);
  assert.equal(skillMetadata.skills[0].name, "example");
  assert.equal(skillMetadata.skills[0].source, "project local");
  assert.ok(skillMetadata.skills[0].estimatedTokens > 0);
  assert.ok(skillMetadata.overheadTokens > 0);
  assert.equal(skillMetadata.estimatedTokens, estimateChars(skillPrompt.length));
  assert.deepEqual(estimateSkillMetadata("base", skills).skills, []);
  assert.deepEqual(estimateContextComponents("1234", entries, 12, skillMetadata.estimatedTokens), {
    systemPrompt: 1,
    skillMetadata: skillMetadata.estimatedTokens,
    loadedSkills: 2,
    toolSchemas: 12,
    messages: 1,
    toolCalls: 1,
    toolResults: 1,
  });
  console.log("context-inspection self-test passed");
}
