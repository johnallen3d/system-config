import { readFile } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildBullet,
  buildSessionRecap,
  parseGeneratedRecap,
  shouldSkipCapture,
  snapshotKey,
  upsertSessionSummary,
} from "./index.ts";

type Fixture = {
  name: string;
  kind: "recap" | "skip" | "upsert" | "key" | "bullet" | "parse";
  [key: string]: any;
};

function countOccurrences(value: string, needle: string): number {
  return value.split(needle).length - 1;
}

function fail(name: string, details: string): never {
  throw new Error(`${name}: ${details}`);
}

function checkRecap(fixture: Fixture) {
  const actual = buildSessionRecap(fixture.branch ?? []);
  const expected = fixture.expected ?? {};
  for (const [key, value] of Object.entries(expected)) {
    if (actual[key as keyof typeof actual] !== value) {
      fail(fixture.name, `expected recap ${key}=${JSON.stringify(value)} got ${JSON.stringify(actual[key as keyof typeof actual])}`);
    }
  }
}

function checkSkip(fixture: Fixture) {
  const actual = shouldSkipCapture(fixture.snapshot, fixture.sessionStartedAtMs ?? 0, fixture.source);
  if (actual !== fixture.expected) {
    fail(fixture.name, `expected skip=${fixture.expected} got ${actual}`);
  }
}

function checkUpsert(fixture: Fixture) {
  const actual = upsertSessionSummary(fixture.existingText, fixture.sessionHeading, fixture.blockLines);
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

function checkKey(fixture: Fixture) {
  const actual = snapshotKey(fixture.snapshotA) === snapshotKey(fixture.snapshotB);
  if (actual !== fixture.expected) {
    fail(fixture.name, `expected key equality=${fixture.expected} got ${actual}`);
  }
}

function checkBullet(fixture: Fixture) {
  const actual = buildBullet(fixture.sessionStartedAtMs ?? 0, fixture.snapshot);
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

function checkParse(fixture: Fixture) {
  const actual = parseGeneratedRecap(fixture.value);
  if (fixture.expected === null) {
    if (actual !== undefined) fail(fixture.name, `expected generated recap rejection, got ${JSON.stringify(actual)}`);
    return;
  }
  for (const [key, value] of Object.entries(fixture.expected ?? {})) {
    if (actual?.[key as keyof typeof actual] !== value) {
      fail(fixture.name, `expected parse ${key}=${JSON.stringify(value)} got ${JSON.stringify(actual?.[key as keyof typeof actual])}`);
    }
  }
}

async function main() {
  const here = dirname(fileURLToPath(import.meta.url));
  const fixturePath = join(here, "session-capture.fixtures.json");
  const fixtures = JSON.parse(await readFile(fixturePath, "utf8")) as Fixture[];

  for (const fixture of fixtures) {
    switch (fixture.kind) {
      case "recap":
        checkRecap(fixture);
        break;
      case "skip":
        checkSkip(fixture);
        break;
      case "upsert":
        checkUpsert(fixture);
        break;
      case "key":
        checkKey(fixture);
        break;
      case "bullet":
        checkBullet(fixture);
        break;
      case "parse":
        checkParse(fixture);
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
