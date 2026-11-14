// agent-log: append one session summary to today's daily-note Agent Log.
// Claude Code calls this through Bash; Pi uses the extension in index.ts.
import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

import { buildBullet, entryFromParts, logTags, readDailyNote, upsertLogEntries } from "./index.ts";

const entry = entryFromParts(process.argv.slice(2).join(" "));
if (!entry) {
  console.error('Usage: agent-log "<one short outcome summary>"');
  process.exit(2);
}

const note = await readDailyNote(new Date(entry.endedAtMs));
if (!note) {
  // Hosts without a vault have nowhere to log; don't make the agent retry.
  console.log("agent-log: no Obsidian vault configured (set PI_SESSION_CAPTURE_VAULT_PATH); nothing logged.");
  process.exit(0);
}

const bullet = buildBullet(entry, logTags(process.env["AGENT_LOG_HARNESS"]?.trim() || "claude"));
const { content, changed } = upsertLogEntries(note.text, [bullet]);
if (changed) {
  await mkdir(dirname(note.path), { recursive: true });
  await writeFile(note.path, content, "utf8");
}
console.log(changed ? `Logged: ${bullet}` : `Already logged: ${bullet}`);
