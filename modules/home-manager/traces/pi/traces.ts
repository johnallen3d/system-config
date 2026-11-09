/**
 * Traces Pi Extension: share tools
 *
 * Registers `traces_share` and `traces_list` so the LLM can share the current
 * session on request. It never reports session activity to traces; automatic
 * sharing lives in a separate extension, traces-agent-hooks.ts, which is
 * installed only when `traces setup` installs agent hooks.
 *
 * Install:
 *   `traces setup agents --skills` composes this template with the shared
 *   helpers and installs .pi/extensions/traces.ts (or globally with --global).
 */
// Vendored from Traces v0.6.45 setup; maintained by system-config.
// Use the exact profile-local session path rather than default-directory discovery.
import { spawn } from "node:child_process";
import { StringEnum } from "@earendil-works/pi-ai";
import { Type } from "typebox";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

type ShareVisibility = "public" | "direct" | "private";

type TracesCommandResult = {
  stdout: string;
  stderr: string;
  exitCode: number | null;
};

function runTraces(
  args: string[],
  options: {
    cwd?: string;
    env?: Record<string, string>;
    stdin?: string;
  } = {},
): Promise<TracesCommandResult> {
  return new Promise((resolve, reject) => {
    const proc = spawn("@traces@", args, {
      cwd: options.cwd,
      env: {
        ...process.env,
        ...options.env,
      },
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 30000,
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    proc.on("error", reject);
    proc.on("close", (exitCode) => {
      resolve({ stdout, stderr, exitCode });
    });

    proc.stdin.end(options.stdin ?? "");
  });
}

function tryParseJson(text: string): any | null {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function textResult(text: string, details: Record<string, unknown> = {}) {
  return {
    content: [{ type: "text", text }],
    details,
  };
}

export default function tracesExtension(pi: ExtensionAPI): void {
  const inheritedTraceId = process.env.TRACES_CURRENT_TRACE_ID;
  const inheritedAgent = process.env.TRACES_CURRENT_AGENT;
  const inheritedSourcePath = process.env.TRACES_CURRENT_SOURCE_PATH;

  function exposeSessionIdentity(sessionId: string, sourcePath?: string): void {
    // Pi's session id is the trace id, so every tool subprocess can identify
    // the exact session without guessing from recency.
    process.env.TRACES_CURRENT_TRACE_ID = sessionId;
    process.env.TRACES_CURRENT_AGENT = "pi";
    if (sourcePath) process.env.TRACES_CURRENT_SOURCE_PATH = sourcePath;
    else delete process.env.TRACES_CURRENT_SOURCE_PATH;
  }

  function restoreInheritedIdentity(): void {
    if (inheritedTraceId === undefined) delete process.env.TRACES_CURRENT_TRACE_ID;
    else process.env.TRACES_CURRENT_TRACE_ID = inheritedTraceId;
    if (inheritedAgent === undefined) delete process.env.TRACES_CURRENT_AGENT;
    else process.env.TRACES_CURRENT_AGENT = inheritedAgent;
    if (inheritedSourcePath === undefined) delete process.env.TRACES_CURRENT_SOURCE_PATH;
    else process.env.TRACES_CURRENT_SOURCE_PATH = inheritedSourcePath;
  }

  function getSessionId(ctx: any): string | null {
    const sid = ctx?.sessionManager?.getSessionId?.();
    return typeof sid === "string" && sid.length > 0 ? sid : null;
  }

  let currentSessionId: string | null = null;

  pi.on("session_start", (_event: any, ctx: any) => {
    const sid = getSessionId(ctx);
    if (!sid) return;
    currentSessionId = sid;
    exposeSessionIdentity(sid, ctx.sessionManager.getSessionFile?.());
  });

  pi.on("session_shutdown", () => {
    currentSessionId = null;
    restoreInheritedIdentity();
  });

  pi.registerTool({
    name: "traces_share",
    label: "Share to Traces",
    description:
      "Share the current coding session to Traces and return the share URL. " +
      "Use when the user asks to share, publish, or export their session.",
    parameters: Type.Object({
      visibility: Type.Optional(
        StringEnum(["public", "direct", "private"] as const, {
          description:
            "Only set if the user explicitly requests a visibility level (e.g. 'share as public'). Omit to use the correct default based on namespace type.",
        }),
      ),
    }),
    async execute(_toolCallId, params, signal) {
      if (signal?.aborted) {
        return textResult("Share cancelled.");
      }

      const input = (params ?? {}) as { visibility?: ShareVisibility };
      const args = ["share", "--agent", "pi", "--json"];
      if (process.env.TRACES_CURRENT_SOURCE_PATH) {
        args.push("--source-path", process.env.TRACES_CURRENT_SOURCE_PATH);
      } else if (currentSessionId) {
        args.push("--trace-id", currentSessionId);
      } else {
        return textResult("Cannot share without the current session ID or source path.");
      }
      if (input.visibility) {
        args.push("--visibility", input.visibility);
      }

      try {
        const env: Record<string, string> = {
          TRACES_CURRENT_AGENT: "pi",
        };
        if (currentSessionId) {
          env.TRACES_CURRENT_TRACE_ID = currentSessionId;
        }

        const result = await runTraces(args, {
          cwd: process.cwd(),
          env,
        });

        const parsed = tryParseJson(result.stdout);
        if (result.exitCode === 0 && parsed?.ok) {
          return textResult(
            `Session shared!\nURL: ${parsed.data.sharedUrl}\nTrace: ${parsed.data.traceId} (${parsed.data.agentId})\nSelected by: ${parsed.data.selectedBy}`,
            { response: parsed.data },
          );
        }

        const errorPayload = tryParseJson(result.stderr) ?? parsed;
        if (errorPayload?.error) {
          return textResult(
            `Share failed (${errorPayload.error.code}): ${errorPayload.error.message}`,
            { response: errorPayload.error },
          );
        }

        return textResult(`Share failed: ${(result.stderr || result.stdout).trim() || "Unknown error"}`);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return textResult(
          `Failed to share: ${message}. Ensure 'traces' CLI is installed and you are logged in.`,
        );
      }
    },
  });

  pi.registerTool({
    name: "traces_list",
    label: "List Traces",
    description:
      "List available traces that can be shared. " +
      "Use to discover sessions before sharing.",
    parameters: Type.Object({
      agent: Type.Optional(
        Type.String({
          description: "Filter by agent ID. Omit to show all.",
        }),
      ),
    }),
    async execute(_toolCallId, params, signal) {
      if (signal?.aborted) {
        return textResult("Trace listing cancelled.");
      }

      const input = (params ?? {}) as { agent?: string };
      const args = ["share", "--list", "--cwd", process.cwd(), "--json"];
      if (input.agent) {
        args.push("--agent", input.agent);
      }

      try {
        const result = await runTraces(args, { cwd: process.cwd() });
        const parsed = tryParseJson(result.stdout);

        if (result.exitCode === 0 && parsed?.ok && parsed.data.traces.length > 0) {
          const lines = parsed.data.traces.map(
            (trace: {
              id: string;
              agentId: string;
              title: string;
              timestamp: number;
              sharedUrl?: string;
            }) => {
              const timestamp = new Date(trace.timestamp).toISOString();
              const shared = trace.sharedUrl ? ` [shared: ${trace.sharedUrl}]` : "";
              return `${timestamp}  ${trace.agentId}  ${trace.id}  ${trace.title}${shared}`;
            },
          );

          return textResult(`Found ${parsed.data.count} trace(s):\n${lines.join("\n")}`, {
            response: parsed.data,
          });
        }

        if (result.exitCode === 0 && parsed?.ok) {
          return textResult("No traces found.", { response: parsed.data });
        }

        const errorPayload = tryParseJson(result.stderr) ?? parsed;
        if (errorPayload?.error) {
          return textResult(
            `Failed to list traces (${errorPayload.error.code}): ${errorPayload.error.message}`,
            { response: errorPayload.error },
          );
        }

        return textResult(
          `Failed to list traces: ${(result.stderr || result.stdout).trim() || "Unknown error"}`,
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return textResult(`Failed to list traces: ${message}`);
      }
    },
  });
}
