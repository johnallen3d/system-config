import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@mariozechner/pi-tui";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

type WindowUsage = {
  label: string;
  usedPercent?: number;
  resetAt?: number;
  windowSeconds?: number;
};
type CodexCredential = { type?: string; access?: string; accountId?: string };
type CodexUsage = { plan?: string; windows: WindowUsage[]; credits?: string; error?: string; fetchedAt?: number };

const GROK_COST_PER_M = { input: 1.00, output: 2.00, cacheRead: 0.20, cacheWrite: 0 }; // grok-build-0.1 api rates; est only (sub rate limits)

function grokCost(u: any): number {
  if (!u) return 0;
  if (u.cost?.total) return u.cost.total;
  const i = ((u.input || 0) * GROK_COST_PER_M.input) / 1_000_000;
  const c = ((u.cacheRead || 0) * GROK_COST_PER_M.cacheRead) / 1_000_000;
  const o = ((u.output || 0) * GROK_COST_PER_M.output) / 1_000_000;
  return i + c + o;
}

function grokSessionCost(ctx: any): number {
  let total = 0;
  for (const entry of ctx.sessionManager.getEntries()) {
    if (entry.type === "message" && entry.message?.role === "assistant") {
      total += grokCost(entry.message.usage);
    }
  }
  return total;
}

const POLL_MS = 60_000;
let codexUsage: CodexUsage | undefined;
let lastCodexFetch = 0;
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

function grokProvider(ctx: any): boolean {
  const p = ctx.model?.provider;
  return p === "pi-grok-build" || p === "grok-build" || ctx.model?.baseUrl === "pi-grok-build";
}

function authStorageCandidatePaths(homeDir = homedir()): Array<string | undefined> {
  const activePiDir = process.env["PI_CODING_AGENT_DIR"]?.trim();
  return [...new Set([
    activePiDir ? join(activePiDir, "auth.json") : undefined,
    join(homeDir, ".config", "pi-work", "auth.json"),
    join(homeDir, ".config", "pi", "auth.json"),
  ])];
}

function readCodexCredential(paths = authStorageCandidatePaths()): CodexCredential | undefined {
  for (const authPath of paths) {
    if (!authPath || !existsSync(authPath)) continue;
    try {
      const credential = JSON.parse(readFileSync(authPath, "utf8"))?.["openai-codex"];
      if (credential && typeof credential === "object") return credential;
    } catch {
      // Try next profile.
    }
  }
  return undefined;
}

async function fetchCodexUsage(_ctx: any, force = false): Promise<void> {
  const now = Date.now();
  if (!force && now - lastCodexFetch < POLL_MS) return;
  lastCodexFetch = now;
  try {
    const credential = readCodexCredential();
    const access = credential?.type === "oauth" ? credential.access : undefined;
    if (!access) throw new Error("credential not found");
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

function sessionCost(ctx: any): number {
  let total = 0;
  for (const entry of ctx.sessionManager.getEntries()) {
    if (entry.type === "message" && entry.message?.role === "assistant") {
      total += entry.message.usage?.cost?.total ?? 0;
    }
  }
  return total;
}

function wrapPlainText(text: string, width: number): string[] {
  if (width <= 0) return [text];
  if (visibleWidth(text) <= width) return [text];

  const words = text.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? current + " " + word : word;
    if (!current || visibleWidth(candidate) <= width) {
      current = candidate;
      continue;
    }
    lines.push(current);
    current = visibleWidth(word) <= width ? word : truncateToWidth(word, width, "...");
  }

  if (current) lines.push(current);
  return lines.length ? lines : [truncateToWidth(text, width, "...")];
}

function formatWindowUsage(windows: WindowUsage[] | undefined): string {
  return windows?.map(w => {
    const reset = formatResetAt(w.resetAt, w.windowSeconds);
    return w.label + " " + fmtPercent(w.usedPercent) + (reset ? "→" + reset : "");
  }).join(" / ") || "?";
}

function usageText(ctx: any): string {
  const provider = ctx.model?.provider;
  if (provider === "openai-codex") {
    void fetchCodexUsage(ctx);
    if (codexUsage?.error) return "usage: codex " + codexUsage.error;
    const plan = codexUsage?.plan ? codexUsage.plan + " " : "";
    const credits = codexUsage?.credits ? " • " + codexUsage.credits : "";
    return "usage: codex " + plan + formatWindowUsage(codexUsage?.windows) + credits;
  }
  if (grokProvider(ctx)) {
    const cost = grokSessionCost(ctx);
    return "usage: grok $" + cost.toFixed(3) + " est";
  }
  return "usage: $" + sessionCost(ctx).toFixed(3) + " session";
}

const DISABLE_1M_CONTEXT = process.env["CLAUDE_CODE_DISABLE_1M_CONTEXT"] === "1";
const MAX_CONTEXT_TOKENS = DISABLE_1M_CONTEXT ? 200_000 : undefined;

function contextText(ctx: any): { text: string; percent: number | undefined } {
  const usage = ctx.getContextUsage?.();
  const tokens = usage?.tokens;
  const rawLimit = usage?.contextWindow ?? ctx.model?.contextWindow;
  const limit = typeof rawLimit === "number" && MAX_CONTEXT_TOKENS !== undefined
    ? Math.min(rawLimit, MAX_CONTEXT_TOKENS)
    : rawLimit;
  const percent = typeof usage?.percent === "number"
    ? (MAX_CONTEXT_TOKENS !== undefined && typeof tokens === "number" && MAX_CONTEXT_TOKENS > 0
        ? (tokens / MAX_CONTEXT_TOKENS) * 100
        : usage.percent)
    : (typeof tokens === "number" && typeof limit === "number" && limit > 0 ? (tokens / limit) * 100 : undefined);
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
        const usage = usageText(ctx);
        const model = modelText(ctx);

        const lines: string[] = [];
        const wideLeft = theme.fg("dim", usage) + " " + theme.fg("dim", "|") + " " + context;
        const wideRight = theme.fg("dim", model);
        const widePad = " ".repeat(Math.max(1, width - visibleWidth(wideLeft) - visibleWidth(wideRight)));
        const wideLine = wideLeft + widePad + wideRight;

        if (visibleWidth(wideLine) <= width) {
          lines.push(wideLine);
        } else {
          for (const line of wrapPlainText(usage, width)) {
            lines.push(theme.fg("dim", line));
          }
          if (visibleWidth(context) + 3 + visibleWidth(model) <= width) {
            lines.push(context + " " + theme.fg("dim", "|") + " " + theme.fg("dim", model));
          } else {
            lines.push(truncateToWidth(context, width, theme.fg("dim", "...")));
            lines.push(truncateToWidth(theme.fg("dim", model), width, theme.fg("dim", "...")));
          }
        }

        const statuses = Array.from(footerData.getExtensionStatuses().entries())
          .sort(([a], [b]) => String(a).localeCompare(String(b)))
          .map(([, text]) => String(text).replace(/[\r\n\t]/g, " ").replace(/ +/g, " ").trim())
          .filter(Boolean)
          .join(" ");
        if (statuses) {
          for (const line of wrapPlainText(statuses, width)) {
            lines.push(line);
          }
        }
        return lines;
      },
    };
  });
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", (_event, ctx) => {
    installFooter(ctx);
    if (ctx.model?.provider === "openai-codex") void fetchCodexUsage(ctx, true);
  });
  pi.on("model_select", (event, ctx) => {
    if (event.model?.provider === "openai-codex") void fetchCodexUsage(ctx, true);
    requestRender?.();
  });
  pi.on("agent_end", (_event, ctx) => {
    if (ctx.model?.provider === "openai-codex") void fetchCodexUsage(ctx, true);
    requestRender?.();
  });
}
