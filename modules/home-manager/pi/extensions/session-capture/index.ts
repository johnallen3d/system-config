import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export type JournalEntry = {
  summary: string;
  details: string[];
  endedAtMs: number;
};

const OBSIDIAN_BIN = process.env["PI_SESSION_CAPTURE_OBSIDIAN"]?.trim()
  || (process.platform === "darwin" ? "/Applications/Obsidian.app/Contents/MacOS/obsidian" : "obsidian");
const DAILY_VAULT = process.env["PI_SESSION_CAPTURE_VAULT"]?.trim() || "Personal";
const PROFILE = process.env["PI_CODING_AGENT_DIR"]?.endsWith("pi-work") ? "work" : "personal";
const SUMMARY_LIMIT = 100;
const PI_LOG_HEADING = "## Pi Log";
const PROFILE_HEADING = `### ${PROFILE}`;
const PENDING_DIR = join(process.env["HOME"] ?? process.cwd(), ".local", "state", "pi-session-capture", "pending");

export type SessionIdentity = {
  sessionId?: string | null;
  sessionFile?: string | null;
  pendingKey?: string;
};

type PersistedEntry = JournalEntry & {
  profile: string;
  sessionId?: string | null;
  sessionFile?: string | null;
};

type AppendResult = "logged" | "unchanged" | "failed";

export function collapseWhitespace(value: string | undefined | null): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

export function truncate(value: string, limit: number): string {
  if (value.length <= limit) return value;
  return value.slice(0, Math.max(0, limit - 1)).trimEnd() + "…";
}

export function cleanLine(value: string): string {
  return collapseWhitespace(value)
    .replace(/^[-*]\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .replace(/^#+\s*/, "")
    .replace(/^['\"]+|['\"]+$/g, "")
    .trim();
}

export function parseEntry(value: string | undefined | null): JournalEntry | undefined {
  const lines = (value ?? "")
    .split(/\r?\n/)
    .map(cleanLine)
    .filter(Boolean);
  const summary = truncate(lines[0] ?? "", SUMMARY_LIMIT);
  if (!summary) return undefined;
  return {
    summary,
    details: [],
    endedAtMs: Date.now(),
  };
}

export function parseIssueEntry(value: string | undefined | null): JournalEntry | undefined {
  const cleaned = collapseWhitespace(value);
  const match = cleaned.match(/^(\S+)\s+(.+)$/);
  if (!match) return undefined;
  const [, issueId, summary] = match;
  return parseEntry(`captured issue ${issueId}: ${summary}`);
}

export function entryFromParts(summary: string | undefined | null): JournalEntry | undefined {
  const cleanedSummary = truncate(cleanLine(summary ?? ""), SUMMARY_LIMIT);
  if (!cleanedSummary) return undefined;
  return {
    summary: cleanedSummary,
    details: [],
    endedAtMs: Date.now(),
  };
}

export function formatClock(epochMs: number): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(epochMs));
}

export function buildBullet(entry: JournalEntry): string {
  return `- ${formatClock(entry.endedAtMs)} — ${entry.summary}`;
}

export function isChildSessionFile(sessionFile: string | null | undefined): boolean {
  const value = collapseWhitespace(sessionFile);
  if (!value) return false;
  return /\/run-[^/]+\/session\.jsonl$/i.test(value);
}

export function buildPendingKey(sessionId: string | null | undefined, sessionFile: string | null | undefined): string | undefined {
  const value = collapseWhitespace(sessionId) || collapseWhitespace(sessionFile);
  if (!value) return undefined;
  return Buffer.from(value).toString("base64url");
}

export function getSessionIdentity(ctx: any): SessionIdentity {
  const sessionFile = ctx.sessionManager.getSessionFile?.() ?? null;
  const sessionId = ctx.sessionManager.getSessionId?.() ?? ctx.sessionManager.getHeader?.()?.id ?? null;
  return {
    sessionId,
    sessionFile,
    pendingKey: buildPendingKey(sessionId, sessionFile),
  };
}

function pendingPathFor(key: string): string {
  return join(PENDING_DIR, `${key}.json`);
}

async function persistPendingEntry(identity: SessionIdentity | undefined, entry: JournalEntry): Promise<void> {
  if (!identity?.pendingKey) return;
  const payload: PersistedEntry = {
    ...entry,
    profile: PROFILE,
    sessionId: identity.sessionId ?? null,
    sessionFile: identity.sessionFile ?? null,
  };
  await mkdir(PENDING_DIR, { recursive: true });
  await writeFile(pendingPathFor(identity.pendingKey), `${JSON.stringify(payload)}\n`, "utf8");
}

async function clearPendingEntry(identity: SessionIdentity | undefined): Promise<void> {
  if (!identity?.pendingKey) return;
  await rm(pendingPathFor(identity.pendingKey), { force: true });
}

async function readPersistedEntries(): Promise<Array<PersistedEntry & { pendingKey: string }>> {
  try {
    const names = await readdir(PENDING_DIR);
    const results: Array<PersistedEntry & { pendingKey: string }> = [];
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      const pendingKey = name.slice(0, -5);
      try {
        const raw = await readFile(pendingPathFor(pendingKey), "utf8");
        const parsed = JSON.parse(raw) as PersistedEntry;
        if (parsed?.profile !== PROFILE || !parsed?.summary) continue;
        results.push({ ...parsed, pendingKey });
      } catch {
        continue;
      }
    }
    return results;
  } catch {
    return [];
  }
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

function isHeadingLine(value: string | undefined): boolean {
  return /^##+\s+/.test(value ?? "");
}

function trimTrailingBlankLines(lines: string[]): string[] {
  const result = [...lines];
  while (result.length > 0 && result[result.length - 1] === "") result.pop();
  return result;
}

function trimLeadingBlankLines(lines: string[]): string[] {
  const result = [...lines];
  while (result.length > 0 && result[0] === "") result.shift();
  return result;
}

function spliceWithSpacing(lines: string[], insertAt: number, block: string[]): string[] {
  const prefix = lines.slice(0, insertAt);
  const suffix = lines.slice(insertAt);
  const normalizedBlock = [...block];
  const firstBlockLine = normalizedBlock[0];
  const lastBlockLine = normalizedBlock[normalizedBlock.length - 1];

  const normalizedPrefix = isHeadingLine(firstBlockLine)
    ? [...prefix]
    : trimTrailingBlankLines(prefix);
  const previousLine = normalizedPrefix[normalizedPrefix.length - 1];

  if (
    normalizedPrefix.length > 0
    && previousLine !== ""
    && isHeadingLine(firstBlockLine)
  ) {
    normalizedPrefix.push("");
  }

  if (
    normalizedPrefix.length > 0
    && isHeadingLine(previousLine)
    && !isHeadingLine(firstBlockLine)
  ) {
    normalizedPrefix.push("");
  }

  const normalizedSuffix = isHeadingLine(lastBlockLine)
    ? [...suffix]
    : trimLeadingBlankLines(suffix);
  const nextLine = normalizedSuffix[0];

  if (
    normalizedSuffix.length > 0
    && nextLine !== ""
    && lastBlockLine !== ""
    && isHeadingLine(nextLine)
  ) {
    normalizedBlock.push("");
  }

  return [...normalizedPrefix, ...normalizedBlock, ...normalizedSuffix];
}

function ensureTrailingNewline(value: string): string {
  return value.endsWith("\n") ? value : `${value}\n`;
}

export function upsertLogEntries(existingText: string, blockLines: string[]): { content: string; changed: boolean } {
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
  const block = blockLines.join("\n");
  const existingProfile = lines.slice(profileStart + 1, profileEnd).join("\n");
  if (existingProfile.includes(block)) {
    return { content: ensureTrailingNewline(lines.join("\n").trimEnd()), changed: false };
  }

  const nextLines = spliceWithSpacing(lines, profileEnd, blockLines);
  return { content: ensureTrailingNewline(nextLines.join("\n").trimEnd()), changed: true };
}

// Back-compat for older fixtures/imports: sessionHeading is intentionally ignored now.
export function upsertSessionSummary(
  existingText: string,
  _sessionHeading: string,
  blockLines: string[],
): { content: string; changed: boolean } {
  return upsertLogEntries(existingText, blockLines);
}

function encodeObsidianContent(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t");
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

export default function (pi: ExtensionAPI) {
  let pendingEntry: JournalEntry | undefined;
  let lastLoggedBullet: string | undefined;
  let currentSession: SessionIdentity | undefined;

  async function appendEntry(ctx: any, entry: JournalEntry, source: "auto" | "manual"): Promise<AppendResult> {
    const bullet = buildBullet(entry);
    if (lastLoggedBullet === bullet) return "unchanged";

    const dailyNote = await readDailyNote(pi);
    if (!dailyNote) {
      if (ctx.hasUI) ctx.ui.notify(`session-capture ${source} failed`, "warning");
      return "failed";
    }

    const { content, changed } = upsertLogEntries(dailyNote.text, [bullet]);
    if (!changed) {
      lastLoggedBullet = bullet;
      return "unchanged";
    }

    const result = await overwriteDailyNote(pi, dailyNote.path, content, ctx, source);
    if (!result) return "failed";

    lastLoggedBullet = bullet;
    if (ctx.hasUI && source === "manual") ctx.ui.notify("Session summary logged to daily note", "info");
    return "logged";
  }

  async function replayPendingEntries(ctx: any): Promise<void> {
    const entries = await readPersistedEntries();
    for (const entry of entries) {
      const restoredEntry = {
        summary: entry.summary,
        details: entry.details ?? [],
        endedAtMs: entry.endedAtMs ?? Date.now(),
      };
      if (entry.pendingKey === currentSession?.pendingKey) {
        pendingEntry = restoredEntry;
        continue;
      }
      const result = await appendEntry(ctx, restoredEntry, "auto");
      if (result !== "failed") {
        await clearPendingEntry({ pendingKey: entry.pendingKey });
      }
    }
  }

  pi.on("session_start", async (_event, ctx) => {
    pendingEntry = undefined;
    lastLoggedBullet = undefined;
    currentSession = getSessionIdentity(ctx);
    await replayPendingEntries(ctx);
  });

  pi.on("before_agent_start", (event) => ({
    systemPrompt: `${event.systemPrompt}\n\nSession journal capture:\n- If this turn does meaningful work worth remembering, call set_session_summary before final response.\n- Summary must be one short journal bullet, about 8-14 words. No details.\n- Capture outcome/decision only; omit validation, commit hash, file list, tool output, skill lists, and agent inventory.\n- Good: \"Pinned Home Manager to release-26.05 to fix rebuild warning\".\n- Bad: \"Available executable agents: 17\" or \"fix the bugs\".\n- If no meaningful work happened, do not call set_session_summary.`,
  }));

  pi.registerTool({
    name: "set_session_summary",
    label: "Set Session Summary",
    description: "Queue one short journal summary bullet for daily-note capture at shutdown.",
    promptSnippet: "set_session_summary: queue one short journal summary bullet",
    promptGuidelines: [
      "Use set_session_summary when meaningful work happened and should be logged to the journal.",
      "Write one short outcome/decision summary; omit details, validation, commits, raw prompts, tool output, skill lists, and agent inventory.",
    ],
    parameters: {
      type: "object",
      properties: {
        summary: { type: "string", description: "One short journal summary, about 8-14 words. No details." },
      },
      required: ["summary"],
      additionalProperties: false,
    } as any,
    execute: async (_id: string, params: any) => {
      const entry = entryFromParts(params.summary);
      if (!entry) {
        return { content: [{ type: "text" as const, text: "No session summary queued; summary was empty." }], isError: true };
      }
      pendingEntry = entry;
      await persistPendingEntry(currentSession, entry);
      return { content: [{ type: "text" as const, text: "Session summary queued for daily-note capture." }], details: entry };
    },
  });

  pi.on("session_shutdown", async (event, ctx) => {
    if (event.reason === "reload") return;
    if (isChildSessionFile(ctx.sessionManager.getSessionFile?.() ?? null)) return;

    if (!pendingEntry) return;
    const result = await appendEntry(ctx, pendingEntry, "auto");
    if (result !== "failed") {
      await clearPendingEntry(currentSession ?? getSessionIdentity(ctx));
    }
  });

  pi.registerCommand("set-session-summary", {
    description: "Set the journal summary to flush to today's Obsidian daily note at session shutdown",
    handler: async (args: string, ctx: any) => {
      const entry = parseEntry(args);
      if (!entry) {
        if (ctx.hasUI) ctx.ui.notify("Usage: set-session-summary <summary>", "warning");
        return;
      }
      pendingEntry = entry;
      await persistPendingEntry(currentSession ?? getSessionIdentity(ctx), entry);
      if (ctx.hasUI) ctx.ui.notify("Session summary queued for daily note", "info");
    },
  });

  pi.registerCommand("log-session", {
    description: "Append a journal summary to today's Obsidian daily note now",
    handler: async (args: string, ctx: any) => {
      const entry = parseEntry(args);
      if (!entry) {
        if (ctx.hasUI) ctx.ui.notify("Usage: log-session <summary>", "warning");
        return;
      }
      const result = await appendEntry(ctx, entry, "manual");
      if (result !== "failed") {
        pendingEntry = undefined;
        await clearPendingEntry(currentSession ?? getSessionIdentity(ctx));
      }
    },
  });

  pi.registerCommand("log-issue", {
    description: "Append a captured issue summary to today's Obsidian daily note now",
    handler: async (args: string, ctx: any) => {
      const entry = parseIssueEntry(args);
      if (!entry) {
        if (ctx.hasUI) ctx.ui.notify("Usage: log-issue <issue-id> <summary>", "warning");
        return;
      }
      const result = await appendEntry(ctx, entry, "manual");
      if (result !== "failed") {
        pendingEntry = undefined;
        await clearPendingEntry(currentSession ?? getSessionIdentity(ctx));
      }
    },
  });
}
