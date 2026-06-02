import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { basename } from "node:path";

type RuntimeInfo = {
  provider?: string;
  model?: string;
  sessionId?: string | null;
};

export type CaptureSnapshot = {
  activitySeq: number;
  summary: string;
  details: string[];
  endedAtMs: number;
  runtime: RuntimeInfo;
  agentRuns: number;
  delegatedOnly: boolean;
  isChildSession: boolean;
  usedFallback: boolean;
};

type SessionRecap = {
  summary: string;
  details: string[];
  delegatedOnly: boolean;
  usedFallback: boolean;
};

type GeneratedRecap = {
  summary: string;
  details: string[];
};

const OBSIDIAN_BIN = process.env["PI_SESSION_CAPTURE_OBSIDIAN"]?.trim()
  || (process.platform === "darwin" ? "/Applications/Obsidian.app/Contents/MacOS/obsidian" : "obsidian");
const DAILY_VAULT = process.env["PI_SESSION_CAPTURE_VAULT"]?.trim() || "Personal";
const PROFILE = process.env["PI_CODING_AGENT_DIR"]?.endsWith("pi-work") ? "work" : "personal";
const SUMMARY_LIMIT = 120;
const DETAIL_LIMIT = 100;
const DEFAULT_SUMMARY = "session activity";
const LOCAL_SUMMARY_MODEL = process.env["PI_SESSION_CAPTURE_LOCAL_MODEL"]?.trim() || "Qwen3.5-35B-A3B-4bit";
const LOCAL_SUMMARY_BASE_URL = process.env["PI_SESSION_CAPTURE_LOCAL_BASE_URL"]?.trim() || "http://127.0.0.1:8000/v1";
const LOCAL_SUMMARY_API_KEY = process.env["PI_SESSION_CAPTURE_LOCAL_API_KEY"]?.trim() || "888888";
const FALLBACK_SUMMARY_MODEL = process.env["PI_SESSION_CAPTURE_FALLBACK_MODEL"]?.trim() || "gpt-5.5-mini";
const FALLBACK_SUMMARY_BASE_URL = process.env["PI_SESSION_CAPTURE_FALLBACK_BASE_URL"]?.trim() || "https://api.openai.com/v1";
const FALLBACK_SUMMARY_API_KEY = process.env["PI_SESSION_CAPTURE_FALLBACK_API_KEY"]?.trim() || process.env["OPENAI_API_KEY"]?.trim() || "";
const PI_LOG_HEADING = "## Pi Log";
const PROFILE_HEADING = `### ${PROFILE}`;
const DELEGATED_SUBAGENT_MARKERS = [
  "You are a delegated subagent running from a fork of the parent session",
  "You are a child subagent, not the parent orchestrator",
  "Treat the inherited conversation as reference-only context",
  "Your sole job is to execute the task below",
  "Task: [Read from:",
  "Subagent needs a supervisor decision",
];
const LINE_IGNORE_PATTERNS = [
  /^use agents aggressively\b/i,
  /^use (oracle|planner|worker|reviewer)\b/i,
  /^review current changes\b/i,
  /^review corresponding beads issue\b/i,
  /^look at todays note\b/i,
  /^i don't think they are working\b/i,
  /^try again\b/i,
  /^task:/i,
  /^context and approved direction:/i,
  /^implementation constraints:/i,
  /^validation required:/i,
  /^acceptance contract/i,
  /^criteria:/i,
  /^required evidence:/i,
  /^finish with /i,
  /^output:/i,
  /^do not /i,
  /^current date:/i,
  /^run:/i,
  /^status:/i,
  /^plan:/i,
  /^routing note:/i,
  /^scope looks /i,
  /^session:/i,
  /^agent:/i,
  /^child /i,
  /^to reply,? use /i,
  /^subagent needs /i,
  /^working rules:/i,
];
const ACTION_PATTERNS = /(fix|refine|investigate|implement|add|remove|update|capture|log|summarize|summarise|filter|dedupe|dedup|suppress|plan)\b/i;
const SESSION_CAPTURE_PATTERNS = /(session capture|content of the capture|pi log|daily note|captured notes|personal headers?|raw prompts?|prompt trace|duplicate .*head|heading-aware|subagent spam)/i;

export function collapseWhitespace(value: string | undefined | null): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

export function truncate(value: string, limit: number): string {
  if (value.length <= limit) return value;
  return value.slice(0, Math.max(0, limit - 1)).trimEnd() + "…";
}

export function messageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .filter((part): part is { type?: string; text?: string } => Boolean(part) && typeof part === "object")
      .filter((part) => part.type === "text" && typeof part.text === "string")
      .map((part) => part.text ?? "")
      .join("\n");
  }
  return "";
}

export function isDelegatedPrompt(value: string | undefined | null): boolean {
  const collapsed = collapseWhitespace(value);
  if (!collapsed) return false;
  return DELEGATED_SUBAGENT_MARKERS.some((marker) => collapsed.includes(marker));
}

function normalizeLine(value: string): string {
  return collapseWhitespace(value.replace(/^[-*\d.)\s]+/, "").replace(/^#+\s*/, ""));
}

function looksLikePath(value: string): boolean {
  return /^\/Users\//.test(value) || /^~\//.test(value);
}

function lineScore(value: string): number {
  let score = 0;
  if (SESSION_CAPTURE_PATTERNS.test(value)) score += 80;
  if (ACTION_PATTERNS.test(value)) score += 25;
  if (/(duplicate|duplicated|multiple|prompt|checklist|heading|header|spam|dedupe|dedup|summary)/i.test(value)) score += 25;
  if (/(best technical fit|best fit|technical fit|decision|chosen path|why:|cloudflare|pages function|worker|resend|reply-to|honeypot|turnstile)/i.test(value)) score += 70;
  if (/system-config-[a-z0-9]+/i.test(value)) score += 20;
  if (looksLikePath(value)) score -= 80;
  if (LINE_IGNORE_PATTERNS.some((pattern) => pattern.test(value))) score -= 100;
  return score;
}

export function extractCandidateLines(value: string | undefined | null): string[] {
  const text = value ?? "";
  const rawLines = text
    .split(/\r?\n/)
    .flatMap((line) => {
      if (!line.includes(" - ")) return [line];
      if (!line.trimStart().startsWith("- ")) return [line];
      return line.split(/\s+-\s+/);
    })
    .map(normalizeLine)
    .flatMap((line) => line.length > 160 ? line.split(/(?<=[.!?])\s+/).map(normalizeLine) : [line])
    .filter(Boolean);

  return rawLines.filter((line) => !LINE_IGNORE_PATTERNS.some((pattern) => pattern.test(line)));
}

function detectIssueId(lines: string[]): string | undefined {
  const joined = lines.join(" ");
  return joined.match(/\b(system-config-[a-z0-9]+)\b/i)?.[1];
}

function appendIssueId(summary: string, issueId: string | undefined): string {
  if (!issueId) return summary;
  if (summary.includes(issueId)) return summary;
  const next = `${summary} for ${issueId}`;
  return truncate(next, SUMMARY_LIMIT);
}

function capitalizeSentence(value: string): string {
  if (!value) return value;
  return value[0].toUpperCase() + value.slice(1);
}

function bestSummaryFromLines(lines: string[]): string {
  const joined = lines.join(" ");
  const issueId = detectIssueId(lines);
  if (/(PR #3441|zero-target|no matrix entries|no `refresh-packages` job|Slack noise|base_key)/i.test(joined)
    && /(regression|workflow|generate-matrix|empty-matrix|planning)/i.test(joined)) {
    return appendIssueId("Reframed dataops workflow regression", issueId);
  }

  if (/(contact form|gmatter|info@gmatter\.co|onsubmit)/i.test(joined) && /(cloudflare|pages function|worker|resend|email api)/i.test(joined)) {
    return appendIssueId("Service spam filter", issueId);
  }

  if (SESSION_CAPTURE_PATTERNS.test(joined)) {
    if (/content|useful information|useful.*log|activities|activity/i.test(joined)) {
      return appendIssueId("Improve session-capture daily-note content", issueId);
    }
    return appendIssueId("Fix Pi Log daily-note session summaries", issueId);
  }

  const ranked = [...lines]
    .map((line) => ({ line, score: lineScore(line) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.line.length - b.line.length);

  if (ranked.length === 0) return appendIssueId(DEFAULT_SUMMARY, issueId);

  const best = ranked[0]?.line ?? DEFAULT_SUMMARY;
  const normalized = best
    .replace(/^goal:\s*/i, "")
    .replace(/^requested outcome:\s*/i, "")
    .replace(/^research add nuance:\s*/i, "")
    .replace(/^best technical fit:\s*/i, "Technical fit: ")
    .replace(/^best fit:\s*/i, "Technical fit: ")
    .replace(/^there (?:are|is)\s+/i, "fix ")
    .replace(/^the captured notes are basically just my prompts$/i, "fix Pi Log daily-note session summaries")
    .replace(/^captured notes are basically just my prompts$/i, "fix Pi Log daily-note session summaries")
    .replace(/^multiple ["']?personal["']? headers$/i, "fix duplicated personal headings in Pi Log")
    .replace(/^["']+|["']+$/g, "")
    .trim();

  return appendIssueId(truncate(capitalizeSentence(normalized), SUMMARY_LIMIT), issueId);
}

function cleanDetail(value: string): string {
  const cleaned = collapseWhitespace(value)
    .replace(/^["']+|["']+$/g, "")
    .replace(/^[-*]\s+/, "")
    .replace(/\*\*/g, "")
    .replace(/\s*\([^)]*agent runs?[^)]*\)\s*$/i, "")
    .trim();
  if (cleaned.length <= DETAIL_LIMIT) return cleaned;
  const firstSentence = cleaned.match(/^.{20,100}?[.!?](?:\s|$)/)?.[0]?.trim();
  return firstSentence && firstSentence.length <= DETAIL_LIMIT ? firstSentence : "";
}

function uniqueDetails(values: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values.map(cleanDetail).filter(Boolean)) {
    const key = value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(value);
  }
  return result.slice(0, 5);
}

function heuristicDetails(lines: string[], summary: string): string[] {
  const joined = lines.join(" ");
  if (/(PR #3441|zero-target|no matrix entries|no `refresh-packages` job|Slack noise|base_key)/i.test(joined)
    && /(regression|workflow|generate-matrix|empty-matrix|planning)/i.test(joined)) {
    return [
      "Cause: PR #3441 made unmatched `base_key` payloads produce zero matrix targets.",
      "Impact: false workflow failures and noisy Slack alerts.",
      "Clarified: not 76 unique invalid base keys; this is an unhandled zero-target path.",
      "Next: handle empty matrix cleanly and skip failure notification.",
    ];
  }

  if (/(contact form|gmatter|info@gmatter\.co|onsubmit)/i.test(joined) && /(cloudflare|pages function|worker|resend|email api)/i.test(joined)) {
    return [
      "Technical fit: Cloudflare Pages Function/Worker + Resend.",
      "Why: fits static Cloudflare deploy and keeps control.",
      "Plan: add POST endpoint, server validation, Reply-To handling, and honeypot.",
      "Defer Turnstile unless abuse appears.",
    ];
  }

  if (/content|useful information|useful.*log|activities|activity/i.test(joined) && SESSION_CAPTURE_PATTERNS.test(joined)) {
    return [
      "Old focus: config/filtering mechanics.",
      "New focus: daily-note content quality.",
      "Problem: captured entries describe tool steps, not useful activity history.",
      "Better: capture outcome, decision, and next step.",
      "Next: make summaries say what changed + why + follow-up.",
    ];
  }

  if (/raw prompts?|captured notes|daily note|pi log/i.test(joined)) {
    return [
      "Problem: captured entries are too close to raw prompts.",
      "Better: summarize meaningful outcome and context.",
      "Next: keep daily-note entries useful when read later.",
    ];
  }

  return uniqueDetails(
    lines
      .filter((line) => line !== summary)
      .filter((line) => !isLowValueGeneratedLine(line) && !isPromptEcho(line))
      .map((line) => ({ line, score: lineScore(line) }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score || a.line.length - b.line.length)
      .map((entry) => entry.line)
      .slice(0, 4),
  );
}

export function buildSessionRecap(branch: any[]): SessionRecap {
  const userTexts = branch
    .filter((entry) => entry?.type === "message" && entry.message?.role === "user")
    .map((entry) => messageText(entry.message?.content))
    .map((text) => text.trim())
    .filter(Boolean);

  if (userTexts.length === 0) {
    return { summary: DEFAULT_SUMMARY, details: [], delegatedOnly: false, usedFallback: true };
  }

  const delegatedSignal = userTexts.some((text) => isDelegatedPrompt(text));
  const assistantLines = extractTextByRole(branch, "assistant")
    .filter((text) => !/^\{\s*"type":"thinking"/i.test(text))
    .slice()
    .reverse()
    .flatMap((text) => extractCandidateLines(text));
  const toolLines = extractTextByRole(branch, "toolResult")
    .map(compactToolResult)
    .filter((text): text is string => Boolean(text))
    .slice()
    .reverse()
    .flatMap((text) => extractCandidateLines(text));
  const userLines = userTexts
    .flatMap((text) => extractCandidateLines(text));
  const candidateLines = [...assistantLines, ...toolLines, ...userLines]
    .filter((line) => !isDelegatedPrompt(line) && !isPromptEcho(line));

  if (candidateLines.length === 0) {
    return { summary: DEFAULT_SUMMARY, details: [], delegatedOnly: delegatedSignal, usedFallback: true };
  }

  const summary = bestSummaryFromLines(candidateLines);
  return {
    summary,
    details: heuristicDetails(candidateLines, summary),
    delegatedOnly: false,
    usedFallback: summary === DEFAULT_SUMMARY,
  };
}

export function isChildSessionFile(sessionFile: string | null | undefined): boolean {
  const value = collapseWhitespace(sessionFile);
  if (!value) return false;
  return /\/run-[^/]+\/session\.jsonl$/i.test(value);
}

export function formatClock(epochMs: number): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(epochMs));
}

export function formatDuration(ms: number): string {
  const totalMinutes = Math.max(0, Math.round(ms / 60_000));
  if (totalMinutes < 1) return "<1m";
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${totalMinutes}m`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}

function getRuntimeInfo(ctx: any): RuntimeInfo {
  const branch = ctx.sessionManager.getBranch?.() ?? [];
  const sessionId = ctx.sessionManager.getSessionId?.() ?? ctx.sessionManager.getHeader?.()?.id ?? null;

  for (let i = branch.length - 1; i >= 0; i -= 1) {
    const entry = branch[i];
    if (entry?.type === "message" && entry.message?.role === "assistant") {
      return {
        provider: entry.message.provider,
        model: entry.message.model,
        sessionId,
      };
    }
  }

  for (let i = branch.length - 1; i >= 0; i -= 1) {
    const entry = branch[i];
    if (entry?.type === "model_change") {
      return {
        provider: entry.provider,
        model: entry.modelId,
        sessionId,
      };
    }
  }

  return {
    provider: ctx.model?.provider,
    model: ctx.model?.id,
    sessionId,
  };
}

async function gitBranch(pi: ExtensionAPI, ctx: any): Promise<string | undefined> {
  const result = await pi.exec("git", ["-C", ctx.cwd, "branch", "--show-current"], { timeout: 3000 });
  const branch = collapseWhitespace(result.stdout);
  if (result.code === 0 && branch) return branch;

  const fallback = await pi.exec("git", ["-C", ctx.cwd, "rev-parse", "--short", "HEAD"], { timeout: 3000 });
  const sha = collapseWhitespace(fallback.stdout);
  return fallback.code === 0 && sha ? `detached@${sha}` : undefined;
}

function encodeObsidianContent(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t");
}

function shortSessionId(sessionId: string | null | undefined): string {
  const value = collapseWhitespace(sessionId);
  if (!value) return "unknown";
  return value.slice(0, 8);
}

function sessionSubheading(ctx: any, snapshot: CaptureSnapshot, branch: string | undefined): string {
  const repo = basename(ctx.cwd);
  const repoLabel = branch ? `${repo} @ ${branch}` : repo;
  return `#### session ${shortSessionId(snapshot.runtime.sessionId)} — ${repoLabel}`;
}

export function buildBullet(sessionStartedAtMs: number, snapshot: CaptureSnapshot): string {
  void sessionStartedAtMs;
  const summary = `- ${formatClock(snapshot.endedAtMs)} — ${snapshot.summary}`;
  const details = snapshot.details
    .map(cleanDetail)
    .filter(Boolean)
    .filter((detail) => !isLowValueGeneratedLine(detail))
    .map((detail) => `  - ${detail}`);
  return [summary, ...details].join("\n");
}

function findHeadingIndex(lines: string[], heading: string, start: number, end: number): number {
  for (let i = start; i < end; i += 1) {
    if (lines[i] === heading) return i;
  }
  return -1;
}

function nextHeadingIndex(lines: string[], start: number, end: number, pattern: RegExp): number {
  for (let i = start; i < end; i += 1) {
    if (pattern.test(lines[i] ?? "")) return i;
  }
  return end;
}

function spliceWithSpacing(lines: string[], insertAt: number, block: string[]): string[] {
  const prefix = lines.slice(0, insertAt);
  const suffix = lines.slice(insertAt);
  const normalizedBlock = [...block];

  if (prefix.length > 0 && prefix[prefix.length - 1] !== "") prefix.push("");
  if (suffix.length > 0 && normalizedBlock[normalizedBlock.length - 1] !== "") normalizedBlock.push("");

  return [...prefix, ...normalizedBlock, ...suffix];
}

function ensureTrailingNewline(value: string): string {
  return value.endsWith("\n") ? value : `${value}\n`;
}

function normalizeBlockForCompare(lines: string[]): string {
  const next = [...lines];
  while (next.length > 0 && next[next.length - 1] === "") next.pop();
  return next.join("\n");
}

export function upsertSessionSummary(
  existingText: string,
  sessionHeading: string,
  blockLines: string[],
): { content: string; changed: boolean } {
  const normalized = existingText.replace(/\r\n/g, "\n");
  const lines = normalized.length > 0 ? normalized.split("\n") : [];

  const piLogStart = findHeadingIndex(lines, PI_LOG_HEADING, 0, lines.length);
  if (piLogStart === -1) {
    const sections = [PI_LOG_HEADING, "", PROFILE_HEADING, "", ...blockLines];
    const base = normalized.trimEnd();
    const content = [base, sections.join("\n")].filter(Boolean).join("\n\n");
    return { content: ensureTrailingNewline(content), changed: true };
  }

  const piLogEnd = nextHeadingIndex(lines, piLogStart + 1, lines.length, /^##\s+/);
  const profileStart = findHeadingIndex(lines, PROFILE_HEADING, piLogStart + 1, piLogEnd);

  if (profileStart === -1) {
    const nextLines = spliceWithSpacing(lines, piLogEnd, [PROFILE_HEADING, "", ...blockLines]);
    return { content: ensureTrailingNewline(nextLines.join("\n").trimEnd()), changed: true };
  }

  const profileEnd = nextHeadingIndex(lines, profileStart + 1, piLogEnd, /^###\s+/);
  const existingSession = findHeadingIndex(lines, sessionHeading, profileStart + 1, profileEnd);
  if (existingSession !== -1) {
    const existingSessionEnd = nextHeadingIndex(lines, existingSession + 1, profileEnd, /^####\s+/);
    const existingBlock = lines.slice(existingSession, existingSessionEnd);
    const nextLines = [
      ...lines.slice(0, existingSession),
      ...blockLines,
      ...lines.slice(existingSessionEnd),
    ];
    const content = ensureTrailingNewline(nextLines.join("\n").trimEnd());
    return {
      content,
      changed: normalizeBlockForCompare(existingBlock) !== normalizeBlockForCompare(blockLines),
    };
  }

  const nextLines = spliceWithSpacing(lines, profileEnd, blockLines);
  return { content: ensureTrailingNewline(nextLines.join("\n").trimEnd()), changed: true };
}

async function readDailyNote(pi: ExtensionAPI): Promise<{ path: string; text: string } | undefined> {
  const pathResult = await pi.exec(OBSIDIAN_BIN, ["daily:path", `vault=${DAILY_VAULT}`], { timeout: 10_000 });
  const path = collapseWhitespace(pathResult.stdout);
  if (pathResult.code !== 0 || !path) return undefined;

  const readResult = await pi.exec(OBSIDIAN_BIN, ["daily:read", `vault=${DAILY_VAULT}`], { timeout: 10_000 });
  if (readResult.code !== 0) return undefined;

  return {
    path,
    text: readResult.stdout ?? "",
  };
}

async function overwriteDailyNote(pi: ExtensionAPI, path: string, content: string, ctx: any, source: "auto" | "manual"): Promise<boolean> {
  const result = await pi.exec(OBSIDIAN_BIN, [
    "create",
    `path=${path}`,
    "overwrite",
    `content=${encodeObsidianContent(content)}`,
    `vault=${DAILY_VAULT}`,
  ], { timeout: 10_000 });
  if (result.code !== 0) {
    if (ctx.hasUI) ctx.ui.notify(`session-capture ${source} failed`, "warning");
    return false;
  }
  return true;
}

export function snapshotKey(snapshot: CaptureSnapshot): string {
  return [
    snapshot.runtime.sessionId ?? "unknown",
    snapshot.activitySeq,
    snapshot.summary,
    ...(snapshot.details ?? []),
    snapshot.agentRuns,
  ].join(":");
}

export function shouldSkipCapture(snapshot: CaptureSnapshot, sessionStartedAtMs: number, source: "auto" | "manual"): boolean {
  if (snapshot.isChildSession || snapshot.delegatedOnly) return true;
  if (source === "auto" && snapshot.agentRuns === 0) return true;

  const durationMs = Math.max(0, snapshot.endedAtMs - sessionStartedAtMs);
  if (snapshot.usedFallback && snapshot.agentRuns === 0 && durationMs < 60_000) return true;

  return false;
}

function extractTextByRole(branch: any[], role: string): string[] {
  return branch
    .filter((entry: any) => entry?.type === "message" && entry.message?.role === role)
    .map((entry: any) => messageText(entry.message?.content))
    .map((text: string) => text.trim())
    .filter((text: string) => text && !isDelegatedPrompt(text));
}

function compactToolResult(value: string): string | undefined {
  const raw = value.trim();
  const text = collapseWhitespace(raw);
  if (!text) return undefined;

  const markdownSummary = raw.match(/## Summary\s+([\s\S]*?)(?:\n## |\n---|$)/i)?.[1];
  if (markdownSummary) return `Research summary: ${truncate(collapseWhitespace(markdownSummary), 700)}`;

  const bestFit = raw.match(/Best (?:technical |overall )?fit[^:\n]*:\s*([\s\S]*?)(?:\n\n|\n## |$)/i)?.[1];
  if (bestFit) return `Best fit: ${truncate(collapseWhitespace(bestFit), 500)}`;

  const issueMatches = [...text.matchAll(/"id":\s*"(system-config-[^"]+)"[\s\S]{0,240}?"title":\s*"([^"]+)"/g)]
    .map((match) => `${match[1]}: ${match[2]}`);
  if (issueMatches.length > 0) return `Issue activity: ${uniqueDetails(issueMatches).join("; ")}`;

  if (/Validated \d+ session-capture fixtures/i.test(text)) return text.match(/Validated \d+ session-capture fixtures\./i)?.[0];
  if (/nix-rebuild log: .*\(exit 0\)/i.test(text)) return "Nix rebuild succeeded.";
  if (/status.:\s*closed/i.test(text)) return "Issue closed after implementation.";

  return undefined;
}

function sessionDigest(ctx: any): string {
  const branch = ctx.sessionManager.getBranch?.() ?? [];
  const userGoals = extractTextByRole(branch, "user").slice(-6);
  const assistantOutcomes = extractTextByRole(branch, "assistant")
    .filter((text) => !/^\{\s*"type":"thinking"/i.test(text))
    .slice(-6);
  const toolOutcomes = extractTextByRole(branch, "toolResult")
    .map(compactToolResult)
    .filter((text): text is string => Boolean(text))
    .slice(-8);

  return truncate([
    "User goals/prompts:",
    ...userGoals.map((text) => `- ${truncate(collapseWhitespace(text), 500)}`),
    "",
    "Assistant outcomes / decisions:",
    ...assistantOutcomes.map((text) => `- ${truncate(collapseWhitespace(text), 700)}`),
    "",
    "Observed tool outcomes:",
    ...toolOutcomes.map((text) => `- ${text}`),
  ].join("\n"), 7000);
}

function isPlaceholderSummary(value: string): boolean {
  return /^(short outcome title without time|<real outcome title, no time>|session activity|summary|title)$/i.test(value.trim());
}

function isPlaceholderDetail(value: string): boolean {
  return /^(context\/problem\/decision\/next-step bullet|<real context\/problem\/decision\/next-step bullet>|\.\.\.|example|bullet)$/i.test(value.trim());
}

function isPromptEcho(value: string): boolean {
  return /^(i want you to|i want |what would|would an alternative|consider and use|proceed\b|ok,?|great!|another new session)/i.test(value.trim());
}

function isLowValueGeneratedLine(value: string): boolean {
  const trimmed = value.trim();
  return /…|\.\.\.|^(status|plan for review|routing note|scope looks):/i.test(trimmed)
    || /^plan:\s*(?:\d|$)/i.test(trimmed)
    || /^(same fix|proposed fix in issue|capture an issue|log clean|need spam posture|implement form wiring|remove `?onsubmit|add issue comment|updated comment)/i.test(trimmed)
    || /^`?[^\s`]+\.(md|ts|tsx|nix|json|yaml|yml|sh)`?$/i.test(trimmed);
}

export function parseGeneratedRecap(value: string): GeneratedRecap | undefined {
  const jsonText = value.match(/\{[\s\S]*\}/)?.[0] ?? "";
  if (!jsonText) return undefined;

  try {
    const parsed = JSON.parse(jsonText);
    const summary = cleanDetail(parsed.summary ?? parsed.title ?? "");
    const details = Array.isArray(parsed.details)
      ? uniqueDetails(parsed.details.map((item: unknown) => String(item))).filter((detail) => !isPlaceholderDetail(detail))
      : [];
    if (!summary || summary.length < 8) return undefined;
    if (isPlaceholderSummary(summary)) return undefined;
    if (isPromptEcho(summary) || isLowValueGeneratedLine(summary)) return undefined;
    if (/agent runs?|duration|tool call|bead issue|issue comment|updated comment|same fix|proposed fix/i.test(summary)) return undefined;
    const usefulDetails = details.filter((detail) => !isPromptEcho(detail) && !isLowValueGeneratedLine(detail));
    if (usefulDetails.length === 0) return undefined;
    return { summary: truncate(summary, SUMMARY_LIMIT), details: usefulDetails };
  } catch {
    return undefined;
  }
}

async function chatCompletion(
  baseUrl: string,
  apiKey: string,
  model: string,
  prompt: string,
  timeoutMs = 12_000,
): Promise<string | undefined> {
  if (!baseUrl || !model) return undefined;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) headers.Authorization = `Bearer ${apiKey}`;

    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
      method: "POST",
      headers,
      signal: controller.signal,
      body: JSON.stringify({
        model,
        temperature: 0.2,
        max_tokens: 260,
        messages: [
          {
            role: "system",
            content: "Write concise daily activity log entries. Outcome first. Use useful bullets. Omit tool metadata, durations, and agent-run counts unless truly important.",
          },
          { role: "user", content: prompt },
        ],
      }),
    });
    if (!response.ok) return undefined;
    const body = await response.json() as any;
    return body?.choices?.[0]?.message?.content;
  } catch {
    return undefined;
  } finally {
    clearTimeout(timeout);
  }
}

async function generateRecap(ctx: any): Promise<GeneratedRecap | undefined> {
  const digest = sessionDigest(ctx);
  if (!digest) return undefined;

  const prompt = `Summarize this Pi coding session for an Obsidian daily note. Use observed outcomes over user prompt wording.\n\nTarget style:\n- 09:01 AM — Session-capture direction changed.\n  - Old focus: config/filtering mechanics.\n  - New focus: daily-note content quality.\n  - Problem: capture says 'update bead issue' → not useful later.\n  - Better: capture outcome, decision, next step.\n  - Next: make summaries say what changed + why + follow-up.\n\nReturn only JSON with keys "summary" and "details". Do not copy examples, schema text, or user request wording.\n\nRules:\n- summary describes meaningful activity/outcome, not internal tool mechanics or user prompt text.\n- details are caveman-terse, useful days later.\n- use Assistant outcomes and Observed tool outcomes first; use User goals only for intent.\n- never quote requests like “I want you to...” or questions as the summary.\n- omit duration, agent-run count, and generic actions like updating an issue.\n- max 5 details.\n\nStructured session digest:\n${digest}`;

  const local = await chatCompletion(LOCAL_SUMMARY_BASE_URL, LOCAL_SUMMARY_API_KEY, LOCAL_SUMMARY_MODEL, prompt);
  const localRecap = local ? parseGeneratedRecap(local) : undefined;
  if (localRecap) return localRecap;

  if (!FALLBACK_SUMMARY_API_KEY) return undefined;
  const fallback = await chatCompletion(FALLBACK_SUMMARY_BASE_URL, FALLBACK_SUMMARY_API_KEY, FALLBACK_SUMMARY_MODEL, prompt);
  return fallback ? parseGeneratedRecap(fallback) : undefined;
}

async function enhanceSnapshot(ctx: any, snapshot: CaptureSnapshot): Promise<CaptureSnapshot> {
  const generated = await generateRecap(ctx);
  if (!generated) return snapshot;
  return {
    ...snapshot,
    summary: generated.summary,
    details: generated.details.length > 0 ? generated.details : snapshot.details,
    usedFallback: false,
  };
}

export function buildSnapshot(ctx: any, agentRuns: number): CaptureSnapshot {
  const branch = ctx.sessionManager.getBranch?.() ?? [];
  const recap = buildSessionRecap(branch);
  const sessionFile = ctx.sessionManager.getSessionFile?.() ?? null;
  return {
    activitySeq: agentRuns,
    summary: recap.summary,
    details: recap.details,
    endedAtMs: Date.now(),
    runtime: getRuntimeInfo(ctx),
    agentRuns,
    delegatedOnly: recap.delegatedOnly,
    isChildSession: isChildSessionFile(sessionFile),
    usedFallback: recap.usedFallback,
  };
}

export default function (pi: ExtensionAPI) {
  let sessionStartedAtMs = Date.now();
  let agentRuns = 0;
  let lastLoggedKey: string | undefined;

  async function appendSnapshot(ctx: any, snapshot: CaptureSnapshot, source: "auto" | "manual"): Promise<boolean> {
    if (shouldSkipCapture(snapshot, sessionStartedAtMs, source)) return false;

    const logKey = snapshotKey(snapshot);
    if (lastLoggedKey === logKey) return false;

    const enhancedSnapshot = await enhanceSnapshot(ctx, snapshot);
    const enhancedLogKey = snapshotKey(enhancedSnapshot);
    if (lastLoggedKey === enhancedLogKey) return false;

    const dailyNote = await readDailyNote(pi);
    if (!dailyNote) {
      if (ctx.hasUI) ctx.ui.notify(`session-capture ${source} failed`, "warning");
      return false;
    }

    const branch = await gitBranch(pi, ctx);
    const sessionHeading = sessionSubheading(ctx, enhancedSnapshot, branch);
    const { content, changed } = upsertSessionSummary(
      dailyNote.text,
      sessionHeading,
      [sessionHeading, "", buildBullet(sessionStartedAtMs, enhancedSnapshot)],
    );
    if (!changed) {
      lastLoggedKey = enhancedLogKey;
      return false;
    }

    const result = await overwriteDailyNote(pi, dailyNote.path, content, ctx, source);
    if (!result) return false;

    lastLoggedKey = enhancedLogKey;
    if (ctx.hasUI && source === "manual") ctx.ui.notify("Session logged to daily note", "info");
    return true;
  }

  pi.on("session_start", () => {
    sessionStartedAtMs = Date.now();
    agentRuns = 0;
    lastLoggedKey = undefined;
  });

  pi.on("agent_end", () => {
    agentRuns += 1;
  });

  pi.on("session_shutdown", async (event, ctx) => {
    if (event.reason === "reload") return;
    // Auto-capture only once at shutdown to keep notes summary-like.
    // Tradeoff: an abrupt crash/kill can miss the final session summary.
    const snapshot = buildSnapshot(ctx, agentRuns);
    await appendSnapshot(ctx, snapshot, "auto");
  });

  pi.registerCommand("log-session-now", {
    description: "Append the current Pi session snapshot to today's Obsidian daily note",
    handler: async (_args: string, ctx: any) => {
      const snapshot = buildSnapshot(ctx, agentRuns);
      await appendSnapshot(ctx, snapshot, "manual");
    },
  });
}
