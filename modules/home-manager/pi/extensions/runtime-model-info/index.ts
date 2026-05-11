import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "@sinclair/typebox";

type RuntimeInfo = {
  source: "assistant-message" | "model_change" | "ctx.model" | "none";
  provider?: string;
  model?: string;
  modelId?: string;
  api?: string;
  responseId?: string;
  assistantMessageId?: string;
  entryTimestamp?: string;
  messageTimestamp?: number;
  sessionFile?: string | null;
  sessionId?: string | null;
  selectedProvider?: string;
  selectedModel?: string;
  selectedContextWindow?: number;
};

function getRuntimeInfo(ctx: any): RuntimeInfo {
  const branch = ctx.sessionManager.getBranch?.() ?? [];
  const selectedProvider = ctx.model?.provider;
  const selectedModel = ctx.model?.id;
  const selectedContextWindow = ctx.model?.contextWindow;
  const sessionFile = ctx.sessionManager.getSessionFile?.() ?? null;
  const sessionId = ctx.sessionManager.getSessionId?.() ?? ctx.sessionManager.getHeader?.()?.id ?? null;

  for (let i = branch.length - 1; i >= 0; i -= 1) {
    const entry = branch[i];
    if (entry?.type === "message" && entry.message?.role === "assistant") {
      return {
        source: "assistant-message",
        provider: entry.message.provider,
        model: entry.message.model,
        modelId: entry.message.model,
        api: entry.message.api,
        responseId: entry.message.responseId,
        assistantMessageId: entry.id,
        entryTimestamp: entry.timestamp,
        messageTimestamp: entry.message.timestamp,
        sessionFile,
        sessionId,
        selectedProvider,
        selectedModel,
        selectedContextWindow,
      };
    }
  }

  for (let i = branch.length - 1; i >= 0; i -= 1) {
    const entry = branch[i];
    if (entry?.type === "model_change") {
      return {
        source: "model_change",
        provider: entry.provider,
        model: entry.modelId,
        modelId: entry.modelId,
        assistantMessageId: entry.id,
        entryTimestamp: entry.timestamp,
        sessionFile,
        sessionId,
        selectedProvider,
        selectedModel,
        selectedContextWindow,
      };
    }
  }

  if (selectedProvider || selectedModel) {
    return {
      source: "ctx.model",
      provider: selectedProvider,
      model: selectedModel,
      modelId: selectedModel,
      sessionFile,
      sessionId,
      selectedProvider,
      selectedModel,
      selectedContextWindow,
    };
  }

  return {
    source: "none",
    sessionFile,
    sessionId,
    selectedProvider,
    selectedModel,
    selectedContextWindow,
  };
}

function formatRuntimeInfo(info: RuntimeInfo): string {
  const lines = [
    `source: ${info.source}`,
    `provider: ${info.provider ?? "unknown"}`,
    `model: ${info.model ?? "unknown"}`,
    `api: ${info.api ?? "unknown"}`,
    `responseId: ${info.responseId ?? "unknown"}`,
    `assistantMessageId: ${info.assistantMessageId ?? "unknown"}`,
    `entryTimestamp: ${info.entryTimestamp ?? "unknown"}`,
    `messageTimestamp: ${info.messageTimestamp ?? "unknown"}`,
    `sessionId: ${info.sessionId ?? "unknown"}`,
    `sessionFile: ${info.sessionFile ?? "ephemeral"}`,
    `selectedModel: ${info.selectedProvider ?? "unknown"}/${info.selectedModel ?? "unknown"}`,
  ];
  return lines.join("\n");
}

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "runtime_model_info",
    label: "Runtime Model Info",
    description:
      "Return reliable runtime metadata for current pi session from assistant messages/session state. " +
      "Use when logging issues or comments and you need actual provider/model info instead of self-reported guesses.",
    parameters: Type.Object({}),
    execute: async (_id: string, _params: any, _signal: any, _onUpdate: any, ctx: any) => {
      const info = getRuntimeInfo(ctx);
      return {
        content: [{ type: "text" as const, text: formatRuntimeInfo(info) }],
        details: info,
      };
    },
  });
}
