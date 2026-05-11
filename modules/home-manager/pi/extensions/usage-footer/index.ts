import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { AuthStorage } from "@earendil-works/pi-coding-agent";
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
