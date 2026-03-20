// OpenCode plugin adapter for ai-intercept
// Intercepts tool calls and delegates policy decisions to ai-intercept.
// Supports both parameter rewrites and tool substitution.
// Exit codes: 0=allow (may rewrite), 2=deny, 3=approve (needs confirmation)
//
// Session approval: OpenCode lacks a post-tool hook, so session approval
// is recorded optimistically at prompt time. If the user denies, the pattern
// is still marked as session-approved. This is a known limitation.

// Session ID: reuse env var or generate one per process
const sessionId = process.env.AI_INTERCEPT_SESSION || `opencode-${process.pid}`;
process.env.AI_INTERCEPT_SESSION = sessionId;

export const AiIntercept = async ({ $ }) => {
  return {
    "tool.execute.before": async (_input, output) => {
      // Extract tool name and input value
      // OpenCode hook context may contain tool info; fallback to detecting from args
      const toolName = output.toolName || _input?.toolName || detectToolName(output.args);
      const inputValue = output.args?.command || output.args?.url || output.args?.path;

      if (!inputValue || !toolName) return;

      // Never intercept ai-intercept's own control commands
      if (/^\s*ai-(?:intercept|approve)\b/.test(inputValue)) return;

      // Build args for session and project support
      const extraArgs = [];
      if (sessionId) extraArgs.push("--session-id", sessionId);
      if (process.env.AI_INTERCEPT_PROJECT) extraArgs.push("--project-dir", process.env.AI_INTERCEPT_PROJECT);

      try {
        // Pass both tool and command/value to ai-intercept for policy evaluation
        const interceptInput = JSON.stringify({
          tool: toolName,
          command: inputValue,
        });

        const result = await $`echo ${interceptInput} | ai-intercept ${extraArgs}`;
        const stdout = result.text().trim();

        if (stdout) {
          const parsed = JSON.parse(stdout);
          if (parsed.decision === "rewrite") {
            // Check if this is a tool substitution (new tool specified)
            if (parsed.tool && parsed.tool !== toolName) {
              // Tool substitution: swap the tool
              return {
                toolName: parsed.tool,
                args: mapToolInput(parsed.tool, parsed.command),
                reason: parsed.reason || "rewritten by policy",
              };
            } else if (parsed.command) {
              // Parameter rewrite: same tool, different input
              output.args = { ...output.args, command: parsed.command };
            }
          }
        }
      } catch (e) {
        if (e.exitCode === 3) {
          // Approve — needs user confirmation; throw so OpenCode prompts
          const parsed = JSON.parse(e.text?.() || e.stdout?.toString() || "{}");

          // Record session approval (optimistic — no post-hook in OpenCode)
          if (parsed.pattern && sessionId) {
            try {
              await $`ai-intercept --session-id ${sessionId} --session-approve ${parsed.pattern}`;
            } catch { /* ignore */ }
          }

          throw new Error(
            `ai-intercept: approval required — ${parsed.reason || "confirm this action"}`,
          );
        }
        if (e.exitCode === 2) {
          // Deny
          throw new Error("Blocked by ai-intercept policy");
        }
        throw e;
      }
    },
  };
};

/**
 * Attempt to detect tool name from the args object structure.
 * OpenCode tools have different arg structures.
 */
function detectToolName(args) {
  if (!args) return null;
  // Heuristics based on common OpenCode tool arg patterns
  if (args.command && typeof args.command === "string") return "Bash";
  if (args.url && typeof args.url === "string") return "WebFetch";
  if (args.file_path || args.filePath) return "Read";
  if (args.content && args.file_path) return "Write";
  return null;
}

/**
 * Map tool input field names based on tool type.
 * Returns appropriate args structure for the target tool.
 *
 * NOTE: Tool substitution in OpenCode requires hooking into tool selection,
 * not just argument rewriting. The return value here may need adjustment
 * based on OpenCode's actual hook capabilities. This implementation assumes
 * OpenCode supports returning a modified toolName from the hook, but this
 * may require additional OpenCode API support.
 */
function mapToolInput(toolName, value) {
  const tool = toolName.toLowerCase();
  if (tool === "bash") {
    return { command: value };
  } else if (tool === "webfetch") {
    return { url: value };
  } else if (tool === "read") {
    return { file_path: value };
  } else if (tool === "write" || tool === "edit") {
    return { file_path: value, content: "" }; // Simplified; real implementation needs more context
  } else if (tool === "glob") {
    return { pattern: value };
  } else if (tool === "grep") {
    return { pattern: value };
  }
  // Fallback: assume 'command' field
  return { command: value };
}
