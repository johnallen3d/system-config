#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const VALID_ID = /^T[1-9]\d*$/;
const TASK_RE = /^- \[([ ~x🔒])\] (T[1-9]\d*) — (.*)$/u;
const LOCK_WAIT_MS = 10;
const LOCK_TIMEOUT_MS = timeoutFromEnv("TASKBOARD_LOCK_TIMEOUT_MS", 5_000);
const LOCK_STALE_MS = 30_000;
const SLEEP_BUFFER = new Int32Array(new SharedArrayBuffer(4));
const SUPACODE_TIMEOUT_MS = timeoutFromEnv("TASKBOARD_SUPACODE_TIMEOUT_MS", 30_000);

function timeoutFromEnv(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined || raw === "") return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${name} must be a positive number of milliseconds`);
  return value;
}

function usage(code = 0) {
  const out = code === 0 ? process.stdout : process.stderr;
  out.write(`Usage: taskboard <command> [options]\n
Commands:
  start [--title TEXT] [--owner NAME] [--side|--bottom|--no-pane] [TASK ...]
  add [--owner NAME] TASK
  doing|done|reopen ID
  block ID [REASON]
  show | path
  open [--side|--bottom]
  close [--remove]
  watch

Global options:
  --state-dir DIR   Override the per-session state directory
  -h, --help        Show help

Environment:
  TASKBOARD_STATE_DIR  Explicit state directory
  TASKBOARD_SESSION    Stable session key outside Supacode
  TASKBOARD_OWNER      Default owner lane (default: Unassigned)
`);
  process.exit(code);
}

function parseArgs(argv) {
  let stateDir;
  const args = [];
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--state-dir") {
      stateDir = argv[++i];
      if (!stateDir) throw new Error("--state-dir requires a directory");
    } else {
      args.push(argv[i]);
    }
  }
  return { stateDir: resolveStateDir(stateDir), args };
}

function resolveStateDir(explicit) {
  if (explicit) return path.resolve(explicit);
  if (process.env.TASKBOARD_STATE_DIR) return path.resolve(process.env.TASKBOARD_STATE_DIR);
  const stateRoot = process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  const supacodeKey = [
    process.env.SUPACODE_WORKTREE_ID,
    process.env.SUPACODE_TAB_ID,
    process.env.SUPACODE_SURFACE_ID,
  ].filter(Boolean).join(":");
  const rawKey = process.env.TASKBOARD_SESSION || supacodeKey || process.cwd();
  const readable = path.basename(process.cwd()).replace(/[^a-zA-Z0-9._-]+/g, "-") || "session";
  const digest = crypto.createHash("sha256").update(rawKey).digest("hex").slice(0, 10);
  return path.join(stateRoot, "taskboard", `${readable}-${digest}`);
}

function pathsFor(stateDir) {
  return {
    stateDir,
    board: path.join(stateDir, "TASKS.md"),
    state: path.join(stateDir, "state.json"),
  };
}

function loadState(files) {
  try {
    return JSON.parse(fs.readFileSync(files.state, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return {};
    throw new Error(`cannot read taskboard state: ${error.message}`);
  }
}

function saveState(files, state) {
  fs.mkdirSync(files.stateDir, { recursive: true });
  writeAtomic(files.state, `${JSON.stringify(state, null, 2)}\n`);
}

function writeAtomic(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(temp, content);
  fs.renameSync(temp, file);
}

function timestamp() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function boardTemplate(title, tasks, owner) {
  const taskLines = tasks.length
    ? tasks.map((task, index) => `- [ ] T${index + 1} — ${singleLine(task)}`)
    : ["- [ ] T1 — Define the first task"];
  return `# ${singleLine(title)}\n\nUpdated: ${timestamp()}\n\n## Tasks\n\n### ${ownerLane(owner)}\n\n${taskLines.join("\n")}\n\n## Notes\n\n- Board is shared across harnesses; keep task IDs stable.\n`;
}

function singleLine(value) {
  return String(value || "").replace(/[\r\n]+/g, " ").trim();
}

function ownerLane(value) {
  return singleLine(value || process.env.TASKBOARD_OWNER || "Unassigned").replaceAll("#", "").trim() || "Unassigned";
}

function requireBoard(files) {
  if (!fs.existsSync(files.board)) {
    throw new Error(`no board found; run 'taskboard start' first (${files.board})`);
  }
  return fs.readFileSync(files.board, "utf8");
}

function updateTimestamp(content) {
  const next = `Updated: ${timestamp()}`;
  if (/^Updated: .*$/m.test(content)) return content.replace(/^Updated: .*$/m, next);
  if (/^# .+$/m.test(content)) return content.replace(/^(# .+)$/m, `$1\n\n${next}`);
  return `${next}\n\n${content}`;
}

function mutateTask(files, id, status, reason = "") {
  if (!VALID_ID.test(id || "")) throw new Error("task ID must look like T1");
  withBoardLock(files, () => {
    const content = requireBoard(files);
    let found = false;
    const lines = content.split("\n").map((line) => {
      const match = line.match(TASK_RE);
      if (!match || match[2] !== id) return line;
      found = true;
      let text = match[3].replace(/ \(blocked: .*\)$/u, "");
      if (status === "🔒") text += ` (blocked: ${singleLine(reason) || "reason not recorded"})`;
      return `- [${status}] ${id} — ${text}`;
    });
    if (!found) throw new Error(`task not found: ${id}`);
    writeAtomic(files.board, updateTimestamp(lines.join("\n")));
  });
}

function addTask(files, text, owner) {
  if (!singleLine(text)) throw new Error("add requires task text");
  const id = withBoardLock(files, () => {
    const content = requireBoard(files);
    const ids = [...content.matchAll(/^- \[[^\]]+\] T([1-9]\d*) — /gmu)].map((match) => Number(match[1]));
    const nextId = `T${Math.max(0, ...ids) + 1}`;
    const line = `- [ ] ${nextId} — ${singleLine(text)}`;
    writeAtomic(files.board, updateTimestamp(insertIntoLane(content, ownerLane(owner), line)));
    return nextId;
  });
  process.stdout.write(`${id}\n`);
}

function insertIntoLane(content, owner, line) {
  const lane = `\n### ${owner}\n`;
  const laneStart = content.indexOf(lane);
  if (laneStart >= 0) {
    const bodyStart = laneStart + lane.length;
    const nextLane = content.indexOf("\n### ", bodyStart);
    const notes = content.indexOf("\n## Notes\n", bodyStart);
    const insertAt = [nextLane, notes, content.length].filter((index) => index >= 0).sort((a, b) => a - b)[0];
    return `${content.slice(0, insertAt).trimEnd()}\n${line}\n${content.slice(insertAt)}`;
  }
  const notes = content.indexOf("\n## Notes\n");
  if (notes < 0) return `${content.trimEnd()}\n\n### ${owner}\n\n${line}\n`;
  return `${content.slice(0, notes).trimEnd()}\n\n### ${owner}\n\n${line}\n${content.slice(notes)}`;
}

function withBoardLock(files, operation) {
  fs.mkdirSync(files.stateDir, { recursive: true });
  const lockFile = path.join(files.stateDir, ".lock");
  const deadline = Date.now() + LOCK_TIMEOUT_MS;
  let fd;
  while (fd === undefined) {
    try {
      fd = createBoardLock(lockFile);
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      removeStaleLock(lockFile);
      if (Date.now() >= deadline) throw new Error(`could not acquire taskboard lock within ${LOCK_TIMEOUT_MS}ms`);
      Atomics.wait(SLEEP_BUFFER, 0, 0, LOCK_WAIT_MS);
    }
  }
  try {
    return operation();
  } finally {
    fs.closeSync(fd);
    removeFile(lockFile);
  }
}

function createBoardLock(lockFile) {
  const fd = fs.openSync(lockFile, "wx");
  try {
    if (process.env.TASKBOARD_TEST_FAIL_LOCK_WRITE === "1") throw new Error("injected lock write failure");
    fs.writeFileSync(fd, `${process.pid}\n`);
    return fd;
  } catch (error) {
    try { fs.closeSync(fd); } catch { /* preserve the original write error */ }
    removeFile(lockFile);
    throw error;
  }
}

function removeStaleLock(lockFile) {
  try {
    if (Date.now() - fs.statSync(lockFile).mtimeMs > LOCK_STALE_MS) fs.unlinkSync(lockFile);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

function resolveCommand(command) {
  const candidates = command.includes(path.sep)
    ? [path.resolve(command)]
    : String(process.env.PATH || "").split(path.delimiter).filter(Boolean).map((dir) => path.join(dir, command));
  for (const candidate of candidates) {
    try {
      fs.accessSync(candidate, fs.constants.X_OK);
      if (fs.statSync(candidate).isFile()) return candidate;
    } catch (error) {
      if (!["ENOENT", "EACCES"].includes(error.code)) throw error;
    }
  }
  return null;
}

function shellQuote(value) {
  return "'" + String(value).replaceAll("'", "'\"'\"'") + "'";
}

function openPane(files, direction) {
  withBoardLock(files, () => {
    requireBoard(files);
    const state = loadState(files);
    if (state.paneId) {
      process.stdout.write(`pane already tracked: ${state.paneId}\n`);
      return;
    }
    const supacode = resolveCommand("supacode");
    if (!supacode || !process.env.SUPACODE_TAB_ID || !process.env.SUPACODE_SURFACE_ID) {
      process.stdout.write(`no Supacode surface available; board: ${files.board}\n`);
      return;
    }
    const command = [
      shellQuote(process.execPath),
      shellQuote(SCRIPT_PATH),
      "watch",
      "--state-dir",
      shellQuote(files.stateDir),
    ].join(" ");
    const args = ["surface", "split"];
    if (process.env.SUPACODE_WORKTREE_ID) args.push("-w", process.env.SUPACODE_WORKTREE_ID);
    args.push("-t", process.env.SUPACODE_TAB_ID, "-s", process.env.SUPACODE_SURFACE_ID, "-d", direction, "-i", command);
    const paneId = execFileSync(supacode, args, { encoding: "utf8", timeout: SUPACODE_TIMEOUT_MS }).trim();
    if (!paneId) throw new Error("Supacode did not return a pane UUID");
    saveState(files, {
      ...state,
      boardPath: files.board,
      worktreeId: process.env.SUPACODE_WORKTREE_ID || null,
      tabId: process.env.SUPACODE_TAB_ID,
      originSurfaceId: process.env.SUPACODE_SURFACE_ID,
      paneId,
      direction,
      updatedAt: timestamp(),
    });
    process.stdout.write(`opened ${direction === "h" ? "side" : "bottom"} pane ${paneId}\n`);
  });
}

function closePane(files, remove) {
  withBoardLock(files, () => {
    const state = loadState(files);
    if (state.paneId) {
      try {
        closeTrackedPane(files, state);
      } catch (error) {
        if (!remove) throw error;
        process.stderr.write(`warning: could not close tracked pane cleanly: ${error.message}\n`);
      }
    } else {
      process.stdout.write("no taskboard pane is tracked\n");
    }
    if (remove) removeBoardFiles(files);
  });
  if (remove) finishBoardRemoval(files);
}

function closeTrackedPane(files, state) {
  const supacode = resolveCommand("supacode");
  if (!supacode) throw new Error("cannot close tracked pane: supacode command not found");
  if (!state.tabId) throw new Error("cannot close tracked pane: saved tab ID is missing");
  const args = ["surface", "close"];
  if (state.worktreeId) args.push("-w", state.worktreeId);
  args.push("-t", state.tabId, "-s", state.paneId);
  execFileSync(supacode, args, { stdio: "inherit", timeout: SUPACODE_TIMEOUT_MS });
  delete state.paneId;
  state.updatedAt = timestamp();
  saveState(files, state);
  process.stdout.write("closed taskboard pane\n");
}

function removeBoardFiles(files) {
  for (const file of [files.board, files.state]) removeFile(file);
}

function finishBoardRemoval(files) {
  try {
    fs.rmdirSync(files.stateDir);
  } catch (error) {
    if (!["ENOENT", "ENOTEMPTY"].includes(error.code)) throw error;
  }
  process.stdout.write("removed taskboard files\n");
}

function removeFile(file) {
  try {
    fs.unlinkSync(file);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

function watch(files) {
  requireBoard(files);
  const render = () => {
    process.stdout.write("\u001b[2J\u001b[H\u001b]0;Taskboard\u0007");
    process.stdout.write(fs.readFileSync(files.board, "utf8"));
  };
  render();
  const timer = setInterval(render, 2000);
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => { clearInterval(timer); process.exit(0); });
}

function parseDirection(args, fallback = "h") {
  if (args.includes("--bottom")) return "v";
  if (args.includes("--side")) return "h";
  return fallback;
}

function startBoard(files, rest) {
  let title = path.basename(process.cwd()) || "Session Taskboard";
  let owner = process.env.TASKBOARD_OWNER || "Unassigned";
  const tasks = [];
  for (let i = 0; i < rest.length; i += 1) {
    if (rest[i] === "--title") {
      title = rest[++i];
      if (!title) throw new Error("--title requires text");
    } else if (rest[i] === "--owner") {
      owner = rest[++i];
      if (!owner) throw new Error("--owner requires a name");
    } else if (!["--side", "--bottom", "--no-pane"].includes(rest[i])) {
      tasks.push(rest[i]);
    }
  }
  withBoardLock(files, () => {
    if (!fs.existsSync(files.board)) writeAtomic(files.board, boardTemplate(title, tasks, owner));
    saveState(files, { ...loadState(files), boardPath: files.board, updatedAt: timestamp() });
  });
  process.stdout.write(`board: ${files.board}\n`);
  if (!rest.includes("--no-pane")) openPane(files, parseDirection(rest));
}

function addTaskCommand(files, args) {
  let owner = process.env.TASKBOARD_OWNER || "Unassigned";
  const text = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--owner") {
      owner = args[++i];
      if (!owner) throw new Error("--owner requires a name");
    } else {
      text.push(args[i]);
    }
  }
  addTask(files, text.join(" "), owner);
}

const COMMANDS = {
  start: startBoard,
  add: addTaskCommand,
  doing: (files, args) => mutateTask(files, args[0], "~"),
  done: (files, args) => mutateTask(files, args[0], "x"),
  reopen: (files, args) => mutateTask(files, args[0], " "),
  block: (files, args) => mutateTask(files, args[0], "🔒", args.slice(1).join(" ")),
  show: (files) => process.stdout.write(requireBoard(files)),
  path: (files) => process.stdout.write(`${files.board}\n`),
  open: (files, args) => openPane(files, parseDirection(args)),
  close: (files, args) => closePane(files, args.includes("--remove")),
  watch,
};

function main() {
  const { stateDir, args } = parseArgs(process.argv.slice(2));
  if (args.includes("-h") || args.includes("--help") || args.length === 0) usage(0);
  const files = pathsFor(stateDir);
  const [command, ...rest] = args;
  const handler = COMMANDS[command];
  if (!handler) throw new Error(`unknown command: ${command}`);
  handler(files, rest);
}

try {
  main();
} catch (error) {
  process.stderr.write(`taskboard: ${error.message}\n`);
  process.exit(1);
}
