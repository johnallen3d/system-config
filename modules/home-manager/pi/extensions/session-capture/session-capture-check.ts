import { chmod, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({ options: { extension: { type: "string" } } });
const {
  default: sessionCapture,
  buildBullet,
  buildPendingKey,
  isChildSessionFile,
  parseEntry,
  parseIssueEntry,
  resolveDailyNotePath,
  upsertLogEntries,
} = await import(values.extension ? pathToFileURL(resolve(values.extension)).href : "./index.ts");

type Fixture = {
  name: string;
  kind: "parse" | "issue" | "upsert" | "bullet" | "child" | "pending-key";
  [key: string]: any;
};

function countOccurrences(value: string, needle: string): number {
  return value.split(needle).length - 1;
}

function fail(name: string, details: string): never {
  throw new Error(`${name}: ${details}`);
}

function checkObject(name: string, actual: any, expected: any) {
  if (expected === null) {
    if (actual !== undefined) fail(name, `expected undefined, got ${JSON.stringify(actual)}`);
    return;
  }
  for (const [key, value] of Object.entries(expected ?? {})) {
    if (JSON.stringify(actual?.[key]) !== JSON.stringify(value)) {
      fail(name, `expected ${key}=${JSON.stringify(value)} got ${JSON.stringify(actual?.[key])}`);
    }
  }
}

function checkParse(fixture: Fixture) {
  checkObject(fixture.name, parseEntry(fixture.value), fixture.expected);
}

function checkIssue(fixture: Fixture) {
  checkObject(fixture.name, parseIssueEntry(fixture.value), fixture.expected);
}

function checkUpsert(fixture: Fixture) {
  const actual = upsertLogEntries(fixture.existingText, fixture.blockLines);
  if (actual.changed !== fixture.expected?.changed) {
    fail(fixture.name, `expected changed=${fixture.expected?.changed} got ${actual.changed}`);
  }
  for (const needle of fixture.expected?.contains ?? []) {
    if (!actual.content.includes(needle)) {
      fail(fixture.name, `missing expected content ${JSON.stringify(needle)}`);
    }
  }
  for (const [needle, count] of Object.entries(fixture.expected?.counts ?? {})) {
    const actualCount = countOccurrences(actual.content, needle);
    if (actualCount !== count) {
      fail(fixture.name, `expected ${JSON.stringify(needle)} count=${count} got ${actualCount}`);
    }
  }
}

function checkBullet(fixture: Fixture) {
  const actual = buildBullet(fixture.entry);
  for (const needle of fixture.expected?.contains ?? []) {
    if (!actual.includes(needle)) {
      fail(fixture.name, `missing expected content ${JSON.stringify(needle)} in ${JSON.stringify(actual)}`);
    }
  }
  for (const needle of fixture.expected?.notContains ?? []) {
    if (actual.includes(needle)) {
      fail(fixture.name, `unexpected content ${JSON.stringify(needle)} in ${JSON.stringify(actual)}`);
    }
  }
}

function checkChild(fixture: Fixture) {
  const actual = isChildSessionFile(fixture.value);
  if (actual !== fixture.expected) {
    fail(fixture.name, `expected child=${fixture.expected} got ${actual}`);
  }
}

function checkPendingKey(fixture: Fixture) {
  const actual = buildPendingKey(fixture.sessionId, fixture.sessionFile);
  if (actual !== fixture.expected) {
    fail(fixture.name, `expected pendingKey=${fixture.expected} got ${actual}`);
  }
}

async function checkColdStartReplay() {
  const home = await mkdtemp(join(tmpdir(), "session-capture-check-"));
  const vault = join(home, "vaults", "Test");
  const originalHome = process.env["HOME"];
  const originalVault = process.env["PI_SESSION_CAPTURE_VAULT"];
  const originalVaultPath = process.env["PI_SESSION_CAPTURE_VAULT_PATH"];
  const originalConfig = process.env["PI_SESSION_CAPTURE_OBSIDIAN_CONFIG"];

  try {
    process.env["HOME"] = home;
    process.env["PI_SESSION_CAPTURE_VAULT"] = "Test";
    delete process.env["PI_SESSION_CAPTURE_VAULT_PATH"];
    delete process.env["PI_SESSION_CAPTURE_OBSIDIAN_CONFIG"];

    await mkdir(join(home, "Library", "Application Support", "obsidian"), { recursive: true });
    await mkdir(join(vault, ".obsidian"), { recursive: true });
    await writeFile(
      join(home, "Library", "Application Support", "obsidian", "obsidian.json"),
      JSON.stringify({ vaults: { test: { path: vault } } }),
    );
    await writeFile(join(vault, ".obsidian", "daily-notes.json"), JSON.stringify({ folder: "journal" }));

    const pendingKey = "previous-session";
    const pendingDir = join(home, ".local", "state", "pi-session-capture", "pending");
    await mkdir(pendingDir, { recursive: true });
    await writeFile(join(pendingDir, `${pendingKey}.json`), JSON.stringify({
      summary: "Replayed without Obsidian running",
      details: [],
      endedAtMs: Date.now(),
      profile: process.env["PI_CODING_AGENT_DIR"]?.endsWith("pi-work") ? "work" : "personal",
    }));

    const events = new Map<string, Function>();
    const warnings: string[] = [];
    const api = {
      exec: () => { throw new Error("Obsidian CLI must not be called"); },
      on: (name: string, handler: Function) => events.set(name, handler),
      registerCommand: () => {},
      registerTool: () => {},
    };
    sessionCapture(api as any);

    await events.get("session_start")?.({}, {
      hasUI: true,
      sessionManager: {
        getSessionFile: () => join(home, "current-session.jsonl"),
        getSessionId: () => "current-session",
      },
      ui: { notify: (message: string, level: string) => level === "warning" && warnings.push(message) },
    });

    const dailyPath = await resolveDailyNotePath(home, "Test");
    if (!dailyPath) fail("cold-start replay", "daily note path was not resolved");
    const content = await readFile(dailyPath, "utf8");
    if (!content.includes("Replayed without Obsidian running")) {
      fail("cold-start replay", "pending summary was not written");
    }
    try {
      await readFile(join(pendingDir, `${pendingKey}.json`), "utf8");
      fail("cold-start replay", "pending summary was not cleared");
    } catch (error: any) {
      if (error?.code !== "ENOENT") throw error;
    }
    if (warnings.length > 0) fail("cold-start replay", `unexpected warnings: ${warnings.join(", ")}`);
    console.log("PASS cold-start replay without Obsidian");
  } finally {
    if (originalHome === undefined) delete process.env["HOME"];
    else process.env["HOME"] = originalHome;
    if (originalVault === undefined) delete process.env["PI_SESSION_CAPTURE_VAULT"];
    else process.env["PI_SESSION_CAPTURE_VAULT"] = originalVault;
    if (originalVaultPath === undefined) delete process.env["PI_SESSION_CAPTURE_VAULT_PATH"];
    else process.env["PI_SESSION_CAPTURE_VAULT_PATH"] = originalVaultPath;
    if (originalConfig === undefined) delete process.env["PI_SESSION_CAPTURE_OBSIDIAN_CONFIG"];
    else process.env["PI_SESSION_CAPTURE_OBSIDIAN_CONFIG"] = originalConfig;
    await rm(home, { recursive: true, force: true });
  }
}

async function checkDeferredCapture() {
  const home = await mkdtemp(join(tmpdir(), "session-capture-deferred-"));
  const envKeys = ["HOME", "XDG_CONFIG_HOME", "PI_SESSION_CAPTURE_VAULT", "PI_SESSION_CAPTURE_VAULT_PATH", "PI_SESSION_CAPTURE_OBSIDIAN_CONFIG"];
  const originalEnv = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]));
  const journal = join(home, "vault", "journal");

  try {
    process.env["HOME"] = home;
    process.env["XDG_CONFIG_HOME"] = join(home, ".config");
    process.env["PI_SESSION_CAPTURE_VAULT"] = "Test";
    delete process.env["PI_SESSION_CAPTURE_VAULT_PATH"];
    delete process.env["PI_SESSION_CAPTURE_OBSIDIAN_CONFIG"];

    const events = new Map<string, Function>();
    const commands = new Map<string, any>();
    const tools = new Map<string, any>();
    const warnings: string[] = [];
    sessionCapture({
      on: (name: string, handler: Function) => events.set(name, handler),
      registerCommand: (name: string, command: any) => commands.set(name, command),
      registerTool: (tool: any) => tools.set(tool.name, tool),
    } as any);
    let sessionId = "deferred-session";
    const ctx = {
      hasUI: true,
      sessionManager: {
        getSessionFile: () => join(home, `${sessionId}.jsonl`),
        getSessionId: () => sessionId,
      },
      ui: { notify: (message: string, level: string) => level === "warning" && warnings.push(message) },
    };
    const pendingPath = (id: string) => join(home, ".local", "state", "pi-session-capture", "pending", `${buildPendingKey(id, null)}.json`);
    const assertPending = async (id: string, summary: string) => {
      if (JSON.parse(await readFile(pendingPath(id), "utf8")).summary !== summary) {
        fail("deferred capture", "pending summary was changed or lost");
      }
    };
    const queue = (summary: string) => tools.get("set_session_summary").execute("test", { summary });
    const start = () => events.get("session_start")!({}, ctx);
    const shutdown = () => events.get("session_shutdown")!({ reason: "exit" }, ctx);

    await start();
    await queue("Retained while journaling is unconfigured");
    await shutdown();
    await assertPending(sessionId, "Retained while journaling is unconfigured");
    sessionId = "new-session";
    await start();
    await assertPending("deferred-session", "Retained while journaling is unconfigured");
    if (warnings.length) fail("deferred capture", `automatic warning without a vault: ${warnings}`);

    await queue("Retained after manual logging is deferred");
    for (const [command, args] of [["log-session", "Manual attempt"], ["log-issue", "741 Manual issue attempt"]]) {
      await commands.get(command).handler(args, ctx);
      await assertPending(sessionId, "Retained after manual logging is deferred");
    }
    if (warnings.length !== 2 || warnings.some((message) => !message.includes("PI_SESSION_CAPTURE_VAULT_PATH"))) {
      fail("deferred capture", `expected actionable manual warnings: ${warnings}`);
    }
    warnings.length = 0;
    await shutdown();
    if (warnings.length) fail("deferred capture", "shutdown should defer quietly");

    // Configuration added later must replay and clear both retained entries.
    process.env["PI_SESSION_CAPTURE_VAULT_PATH"] = join(home, "vault");
    await mkdir(join(home, "vault", ".obsidian"), { recursive: true });
    await writeFile(join(home, "vault", ".obsidian", "daily-notes.json"), JSON.stringify({ folder: "journal" }));
    sessionId = "configured-session";
    await start();
    const dailyPath = await resolveDailyNotePath();
    const content = await readFile(dailyPath!, "utf8");
    for (const summary of ["Retained while journaling is unconfigured", "Retained after manual logging is deferred"]) {
      if (!content.includes(summary)) fail("deferred capture", `missing replayed summary: ${summary}`);
    }
    for (const id of ["deferred-session", "new-session"]) {
      try {
        await readFile(pendingPath(id));
        fail("deferred capture", "replayed entry was not cleared");
      } catch (error: any) {
        if (error?.code !== "ENOENT") throw error;
      }
    }

    // Actual read failures must remain visible, with entries left for retry.
    await queue("Retained after a real journal access failure");
    await rm(dailyPath!);
    await mkdir(dailyPath!);
    await shutdown();
    await assertPending(sessionId, "Retained after a real journal access failure");
    if (!warnings.some((message) => message.includes("auto failed:") && message.includes("EISDIR"))) {
      fail("deferred capture", `read failure was hidden: ${warnings}`);
    }
    await rm(dailyPath!, { recursive: true });
    warnings.length = 0;

    // A readable journal directory can still reject writes.
    await chmod(journal, 0o555);
    await shutdown();
    await assertPending(sessionId, "Retained after a real journal access failure");
    if (!warnings.some((message) => message.includes("auto failed:") && message.includes("EACCES"))) {
      fail("deferred capture", `write failure was hidden: ${warnings}`);
    }
    await chmod(journal, 0o755);
    warnings.length = 0;
    sessionId = "recovery-session";
    await start();
    if (!(await readFile(dailyPath!, "utf8")).includes("Retained after a real journal access failure") || warnings.length) {
      fail("deferred capture", "replay did not recover after the access failure");
    }
    console.log("PASS unconfigured-vault deferral, manual diagnostics, retention, replay, and access failures");
  } finally {
    for (const key of envKeys) {
      if (originalEnv[key] === undefined) delete process.env[key];
      else process.env[key] = originalEnv[key];
    }
    await chmod(journal, 0o755).catch(() => {});
    await rm(home, { recursive: true, force: true });
  }
}

async function main() {
  const here = dirname(fileURLToPath(import.meta.url));
  const fixturePath = join(here, "session-capture.fixtures.json");
  let fixtureText = await readFile(fixturePath, "utf8");
  // Fixtures describe the personal profile and its opposite section. Swap both
  // headings when exercising the work profile, preserving separation checks.
  if (process.env["PI_CODING_AGENT_DIR"]?.endsWith("pi-work")) {
    fixtureText = fixtureText.replace(/### (personal|work)/g, (_, profile) =>
      profile === "personal" ? "### work" : "### personal"
    );
  }
  const fixtures = JSON.parse(fixtureText) as Fixture[];

  for (const fixture of fixtures) {
    switch (fixture.kind) {
      case "parse":
        checkParse(fixture);
        break;
      case "issue":
        checkIssue(fixture);
        break;
      case "upsert":
        checkUpsert(fixture);
        break;
      case "bullet":
        checkBullet(fixture);
        break;
      case "child":
        checkChild(fixture);
        break;
      case "pending-key":
        checkPendingKey(fixture);
        break;
      default:
        fail(fixture.name, `unknown fixture kind ${(fixture as any).kind}`);
    }
    console.log(`PASS ${fixture.name}`);
  }

  await checkColdStartReplay();
  await checkDeferredCapture();
  console.log(`Validated ${fixtures.length} session-capture fixtures plus cold-start replay and vault deferral.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
