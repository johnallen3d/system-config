#!/usr/bin/env node
// Standalone presentation from amfaro/agent-kit 0.59.0 (6a01c99).
// Keep both Claude profiles on this shared renderer; never read profile state.
import { execFileSync } from "node:child_process";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";

const RESET = "\x1b[0m";
const DIM = "\x1b[2m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";

export function formatTokens(count) {
  if (!Number.isFinite(count) || count < 0) return "?";
  if (count < 1000) return String(Math.round(count));
  if (count < 10000) return (count / 1000).toFixed(1) + "k";
  if (count < 1000000) return Math.round(count / 1000) + "k";
  if (count < 10000000) return (count / 1000000).toFixed(1) + "M";
  return Math.round(count / 1000000) + "M";
}

// Input tokens only, matching how Claude Code computes used_percentage.
function contextTokens(usage) {
  if (!usage) return 0;
  return (usage.input_tokens ?? 0)
    + (usage.cache_creation_input_tokens ?? 0)
    + (usage.cache_read_input_tokens ?? 0);
}

export function renderStatusLine(input, { branch, color = true } = {}) {
  const paint = (code, text) => (color ? code + text + RESET : text);
  const window = input?.context_window ?? {};
  const limit = window.context_window_size || 200000;
  const tokens = contextTokens(window.current_usage);
  const percent = typeof window.used_percentage === "number"
    ? window.used_percentage
    : (tokens / limit) * 100;

  const ctxText = `ctx ${formatTokens(tokens)}/${formatTokens(limit)} ${Math.round(percent)}%`;
  const ctx = percent > 90 ? paint(RED, ctxText) : percent > 70 ? paint(YELLOW, ctxText) : ctxText;
  const model = input?.model?.display_name || input?.model?.id;
  const first = model ? `${ctx} ${paint(DIM, "|")} ${paint(DIM, model)}` : ctx;

  const dir = input?.workspace?.current_dir || input?.cwd;
  const name = dir ? basename(dir) : "";
  const location = [name, branch].filter(Boolean).join(" · ");

  return location ? `${first}\n${paint(DIM, location)}` : first;
}

function gitBranch(cwd) {
  if (!cwd) return undefined;
  try {
    return execFileSync("git", ["-C", cwd, "branch", "--show-current"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 1000,
    }).trim() || undefined;
  } catch {
    return undefined;
  }
}

async function main() {
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;
  let input = {};
  try {
    input = JSON.parse(raw);
  } catch {
    // Render defaults rather than break the status line.
  }
  const cwd = input.workspace?.current_dir || input.cwd;
  const branch = gitBranch(cwd) ?? input.worktree?.branch;
  const color = !process.env.NO_COLOR;
  process.stdout.write(renderStatusLine(input, { branch, color }) + "\n");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  await main();
}
