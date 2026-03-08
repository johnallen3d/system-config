// OpenCode plugin adapter for ai-intercept
// Intercepts tool calls and delegates policy decisions to ai-intercept.

export const AiIntercept = async ({ $ }) => {
  return {
    "tool.execute.before": async (_input, output) => {
      const command = output.args?.command;
      if (!command) return;

      try {
        await $`ai-intercept ${command}`;
      } catch {
        throw new Error("Blocked by ai-intercept policy");
      }
    },
  };
};
