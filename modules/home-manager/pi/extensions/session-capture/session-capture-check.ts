import { readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildBullet,
  buildPendingKey,
  isChildSessionFile,
  parseEntry,
  parseIssueEntry,
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

  console.log(`Validated ${fixtures.length} session-capture fixtures.`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
