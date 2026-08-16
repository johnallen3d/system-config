import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const script = join(dirname(fileURLToPath(import.meta.url)), "imark.mjs");

function argsFor(input: string): string[] {
  return input.trim().split(/\s+/).filter(Boolean);
}

function run(command: "notes" | "review", args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [script, command, ...args], { stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.stderr.on("data", (chunk) => { output += chunk; });
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? resolve(output.trim()) : reject(new Error(output.trim() || `imark exited ${code}`)));
  });
}

function register(pi: ExtensionAPI, command: "notes" | "review", description: string) {
  pi.registerCommand(`imark-${command}`, {
    description,
    handler: async (input, ctx) => {
      const args = argsFor(input);
      if (!args.length) {
        ctx.ui.notify(`Usage: /imark-${command} <file.md>${command === "review" ? " [--no-wait]" : " [--all]"}`, "error");
        return;
      }
      try {
        const output = await run(command, args);
        pi.sendMessage({ customType: `imark-${command}`, content: output }, { triggerTurn: true });
      } catch (error) {
        ctx.ui.notify(error instanceof Error ? error.message : String(error), "error");
      }
    },
  });
}

export default function (pi: ExtensionAPI) {
  register(pi, "notes", "Read Imark comments from a Markdown file");
  register(pi, "review", "Open a Markdown file in Imark and wait for review");
}
