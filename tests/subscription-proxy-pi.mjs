// Verify the host's actual Pi runtime/config and session metadata without model calls.
// Usage: PI_CODING_AGENT_DIR=<profile> node tests/subscription-proxy-pi.mjs <runtime-directory>
import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir, homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const runtimeRoot = process.argv[2];
assert(runtimeRoot, "Supply this host's actual Pi runtime directory");
const profile = process.env.PI_CODING_AGENT_DIR;
assert(profile, "Respect PI_CODING_AGENT_DIR explicitly");
const work = profile === join(homedir(), ".config/pi-work");
assert(work || profile === join(homedir(), ".config/pi"));
const moduleUrl = (name) => pathToFileURL(join(runtimeRoot, "dist/core", name)).href;
const { ModelRuntime } = await import(moduleUrl("model-runtime.js"));
const { AuthStorage } = await import(moduleUrl("auth-storage.js"));
const { InMemoryCodingAgentModelsStore } = await import(moduleUrl("models-store.js"));
const options = (modelsPath) => ({modelsPath, credentials: AuthStorage.inMemory(),
  modelsStore: new InMemoryCodingAgentModelsStore(), allowModelNetwork: false});
const runtime = await ModelRuntime.create(options(join(profile, "models.json")));
assert.equal(runtime.getError(), undefined);
const keys = JSON.parse(await readFile(join(homedir(), ".config/subscription-proxy/credentials.json"), "utf8"));
for (const provider of (work ? ["subscription-codex", "subscription-go"] : ["subscription-codex"])) {
  const models = [...runtime.getModels(provider)];
  assert(models.length > 0, `Missing ${provider}`);
  assert(models.every((model) => !model.id.toLowerCase().includes("claude")));
  for (const model of models) {
    const resolution = await runtime.getAuth(model);
    assert.equal(resolution.auth.apiKey, keys.profiles[work ? "work" : "personal"].client);
    assert(model.baseUrl.startsWith(work ? "http://100.97.112.40:8318" : "http://100.97.112.40:8317"));
  }
}
assert.equal(runtime.getModel("subscription-go", "go/glm-5.2") !== undefined, work);
console.log(`PASS actual Pi runtime: ${work ? "work" : "personal"} model definitions and request-time proxy-key resolution; no upstream credentials used`);

// A local synthetic provider proves Pi emits conversation affinity headers and parses tools.
// No traffic is sent to the installed gateway or to an upstream provider.
const temp = await mkdtemp(join(tmpdir(), "subscription-pi-"));
let observed;
const server = createServer(async (req, res) => {
  let raw = "";
  for await (const part of req) raw += part;
  observed = {headers: req.headers, body: JSON.parse(raw)};
  res.writeHead(200, {"content-type": "text/event-stream"});
  res.write('data: {"id":"test","object":"chat.completion.chunk","created":1,"model":"glm-5.2","choices":[{"index":0,"delta":{"role":"assistant","tool_calls":[{"index":0,"id":"call_test","type":"function","function":{"name":"probe","arguments":"{\\\"value\\\":\\\"OK\\\"}"}}]},"finish_reason":null}]}\n\n');
  res.write('data: {"id":"test","object":"chat.completion.chunk","created":1,"model":"glm-5.2","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}\n\n');
  res.end("data: [DONE]\n\n");
});
try {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const installed = JSON.parse(await readFile(join(homedir(), ".config/pi-work/models.json"), "utf8"));
  const go = structuredClone(installed.providers["subscription-go"]);
  go.baseUrl = `http://127.0.0.1:${server.address().port}/v1`;
  go.apiKey = "synthetic-offline-test-key";
  const modelsPath = join(temp, "models.json");
  await writeFile(modelsPath, JSON.stringify({providers: {"subscription-go": go}}));
  const testRuntime = await ModelRuntime.create(options(modelsPath));
  assert.equal(testRuntime.getError(), undefined);
  const model = testRuntime.getModel("subscription-go", "go/glm-5.2");
  const response = await testRuntime.complete(model, {
    messages: [{role: "user", content: [{type: "text", text: "offline test"}], timestamp: 1}],
    tools: [{name: "probe", description: "Synthetic test tool", parameters: {type: "object", properties: {value: {type: "string"}}, required: ["value"]}}],
  }, {sessionId: "subscription-proxy-offline-session", maxTokens: 16, cacheRetention: "short"});
  assert.equal(observed.headers.session_id, "subscription-proxy-offline-session");
  assert(observed.headers["user-agent"].toLowerCase().includes("pi"));
  assert.equal(observed.body.stream, true);
  assert.equal(observed.body.tools[0].function.name, "probe");
  assert(response.content.some((part) => part.type === "toolCall" && part.name === "probe"));
  console.log("PASS actual Pi runtime: synthetic streaming/tool parsing and stable per-conversation session_id emission (no live model calls)");
} finally {
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
  await rm(temp, {recursive: true, force: true});
}
