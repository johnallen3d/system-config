/**
 * Traces Pi Extension: agent hooks
 *
 * Forwards Pi session lifecycle events to `traces hook agent`, which keeps the
 * session's trace shared as it changes. The share tools live in a separate
 * extension, traces.ts.
 *
 * Install:
 *   `traces setup` (or `traces setup --hooks`) composes this template with
 *   shared helpers and writes .pi/extensions/traces-agent-hooks.ts.
 */
// Vendored from Traces v0.6.45 setup; maintained by system-config.
// Use the exact profile-local session path rather than default-directory discovery.
import { spawn } from "node:child_process";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

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

export default function tracesAgentHooks(pi: ExtensionAPI): void {
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

  function callHook(event: string, payload: Record<string, unknown>): void {
    const stdin = JSON.stringify({
      ...payload,
      transcript_path: process.env.TRACES_CURRENT_SOURCE_PATH,
    }) + "\n";
    void runTraces(["hook", "agent", event, "--agent", "pi"], {
      cwd: process.cwd(),
      stdin,
    }).catch(() => {
      // Ignore hook delivery errors to avoid blocking Pi.
    });
  }

  pi.on("session_start", (_event: any, ctx: any) => {
    const sid = getSessionId(ctx);
    if (!sid) return;
    currentSessionId = sid;
    exposeSessionIdentity(sid, ctx.sessionManager.getSessionFile?.());
    callHook("session-start", { session_id: sid });
  });

  pi.on("agent_start", (_event: any, ctx: any) => {
    const sid = getSessionId(ctx) ?? currentSessionId;
    if (!sid) return;
    currentSessionId = sid;
    callHook("prompt-submitted", { session_id: sid });
  });

  function reportAgentDone(ctx: any): void {
    const sid = getSessionId(ctx) ?? currentSessionId;
    if (!sid) return;
    currentSessionId = sid;
    callHook("agent-done", { session_id: sid });
  }

  // Prefer agent_settled: Pi emits agent_end once per attempt from inside its
  // retry/compaction loop, but agent_settled once per prompt from that loop's
  // finally block. Extensions cannot tell a retry from a real ending -- Pi
  // computes `willRetry` but strips it from the event it hands to extensions.
  //
  // agent_settled only exists from Pi 0.80.5, and Pi's loader accepts a
  // subscription to an unknown event without firing it, so agent_end stays
  // registered as the fallback for older Pi. Once a settled event arrives we
  // know this Pi has it, and agent_end stands down for the rest of the session.
  // Session-scoped by design: this extension is instantiated per Pi session, so
  // the flag must stay inside it rather than being hoisted to module scope.
  let sawAgentSettled = false;

  pi.on("agent_settled", (_event: any, ctx: any) => {
    sawAgentSettled = true;
    reportAgentDone(ctx);
  });

  pi.on("agent_end", (_event: any, ctx: any) => {
    if (sawAgentSettled) return;
    reportAgentDone(ctx);
  });

  pi.on("session_shutdown", (_event: any, ctx: any) => {
    const sid = getSessionId(ctx) ?? currentSessionId;
    if (sid) callHook("session-end", { session_id: sid });
    currentSessionId = null;
    restoreInheritedIdentity();
  });
}
