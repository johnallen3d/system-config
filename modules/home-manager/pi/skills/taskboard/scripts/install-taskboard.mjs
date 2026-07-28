#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CLI = path.join(SKILL_DIR, "scripts", "taskboard.mjs");
const INSTALL_HOME = process.env.TASKBOARD_INSTALL_HOME || os.homedir();
const TEST_FAIL_TARGET = process.env.TASKBOARD_TEST_FAIL_TARGET;
const TEST_REPLACE_ROLLBACK_WITH = process.env.TASKBOARD_TEST_REPLACE_ROLLBACK_WITH;
const args = new Set(process.argv.slice(2));
const dryRun = args.has("--dry-run");
const yes = args.has("--yes");
const TARGETS = [
  [path.join(INSTALL_HOME, ".local", "bin", "taskboard"), CLI],
  [path.join(INSTALL_HOME, ".claude", "skills", "taskboard"), SKILL_DIR],
  [path.join(INSTALL_HOME, ".agents", "skills", "taskboard"), SKILL_DIR],
];

if (args.has("-h") || args.has("--help")) {
  process.stdout.write("Usage: install-taskboard.mjs [--dry-run|--yes]\n");
  process.exit(0);
}
if (!dryRun && !yes) throw new Error("pass --yes to install, or --dry-run to preview");

const plan = TARGETS.map(([target, source]) => inspect(target, source));
const conflicts = plan.filter((item) => item.action === "conflict");
if (conflicts.length) {
  throw new Error(`refusing to replace existing path(s): ${conflicts.map((item) => item.target).join(", ")}`);
}
if (dryRun) {
  for (const item of plan) report(item, true);
} else {
  install(plan);
}

function inspect(target, source) {
  if (!fs.existsSync(source)) throw new Error(`missing source: ${source}`);
  if (!pathExists(target)) return { action: "link", target, source };
  const rawLink = fs.lstatSync(target).isSymbolicLink() ? fs.readlinkSync(target) : null;
  const current = rawLink ? path.resolve(path.dirname(target), rawLink) : null;
  return { action: samePath(current, source) ? "linked" : "conflict", target, source };
}

function samePath(first, second) {
  if (!first) return false;
  try {
    return fs.realpathSync(first) === fs.realpathSync(second);
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

function install(plan) {
  const created = [];
  try {
    for (const item of plan) {
      if (item.action === "link") {
        fs.mkdirSync(path.dirname(item.target), { recursive: true });
        if (TEST_FAIL_TARGET === item.target) {
          if (TEST_REPLACE_ROLLBACK_WITH && created[0]) {
            fs.unlinkSync(created[0].target);
            fs.symlinkSync(TEST_REPLACE_ROLLBACK_WITH, created[0].target);
          }
          throw new Error(`injected link failure: ${item.target}`);
        }
        fs.symlinkSync(item.source, item.target);
        created.push(item);
      }
      report(item, false);
    }
  } catch (error) {
    for (let index = created.length - 1; index >= 0; index -= 1) {
      const item = created[index];
      try {
        if (!fs.lstatSync(item.target).isSymbolicLink()) continue;
        if (fs.readlinkSync(item.target) !== item.source) continue;
        fs.unlinkSync(item.target);
      } catch { /* best-effort rollback of links still owned by this run */ }
    }
    throw error;
  }
}

function report(item, preview) {
  if (item.action === "linked") {
    process.stdout.write(`already linked ${item.target}\n`);
  } else {
    process.stdout.write(`${preview ? "[dry-run] link" : "linked"} ${item.target} -> ${item.source}\n`);
  }
}

function pathExists(target) {
  try {
    fs.lstatSync(target);
    return true;
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}
