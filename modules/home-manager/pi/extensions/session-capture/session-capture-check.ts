import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import sessionCapture, {
  buildBullet,
  buildPendingKey,
  isChildSessionFile,
  parseEntry,
  parseIssueEntry,
  resolveDailyNotePath,
  upsertLogEntries,
} from "./index.ts";

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

async function main() {
  const here = dirname(fileURLToPath(import.meta.url));
  const fixturePath = join(here, "session-capture.fixtures.json");
  const fixtures = JSON.parse(await readFile(fixturePath, "utf8")) as Fixture[];

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
  console.log(`Validated ${fixtures.length} session-capture fixtures plus cold-start replay.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
