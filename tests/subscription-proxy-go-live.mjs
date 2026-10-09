// Explicit opt-in live verification: actual Pi runtime, work Go proxy, synthetic tool.
// Usage: mise -C ~/dev/src/amfaro exec -- node <absolute-test-path> <Pi-runtime> [go/model ...]
// Never executed by the catalog refresh jobs. No actual tool is executed.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
assert.equal(process.env.PI_CODING_AGENT_DIR, join(homedir(), '.config/pi-work'));
assert.equal(process.env.CLAUDE_CONFIG_DIR, join(homedir(), '.config/claude-gmatter'));
const root=process.argv[2]; assert(root);
const imp=name=>import(pathToFileURL(join(root,'dist/core',name)).href);
const {ModelRuntime}=await imp('model-runtime.js');
const {AuthStorage}=await imp('auth-storage.js');
const {InMemoryCodingAgentModelsStore}=await imp('models-store.js');
const runtime=await ModelRuntime.create({modelsPath:join(process.env.PI_CODING_AGENT_DIR,'models.json'),credentials:AuthStorage.inMemory(),modelsStore:new InMemoryCodingAgentModelsStore(),allowModelNetwork:false});
assert.equal(runtime.getError(),undefined);
const ids=process.argv.slice(3);
assert(ids.length, 'Explicitly supply models to authorize live calls');
const credentials=JSON.parse(await readFile(join(homedir(),'.config/subscription-proxy/credentials.json'),'utf8'));
for(const id of ids){
 const model=runtime.getModel('subscription-go',id);
 assert(model); assert(id.startsWith('go/') && !id.toLowerCase().includes('claude'));
 assert.equal(model.baseUrl,'http://100.97.112.40:8318/v1');
 assert.equal((await runtime.getAuth(model)).auth.apiKey,credentials.profiles.work.client);
 const stream=runtime.streamSimple(model,{systemPrompt:'Minimal coding-agent gateway test. Follow the user precisely.',messages:[{role:'user',content:[{type:'text',text:'Call the probe tool exactly once with value OK. No other text.'}],timestamp:Date.now()}],tools:[{name:'probe',description:'Synthetic verification only; never executed.',parameters:{type:'object',properties:{value:{type:'string',enum:['OK']}},required:['value'],additionalProperties:false}}]}, {sessionId:'go-live-'+process.platform+'-'+id,reasoning:'low',maxTokens:2048,cacheRetention:'short',signal:AbortSignal.timeout(90000)});
 let events=0; for await(const event of stream)events++;
 const result=await stream.result();
 if(result.stopReason==='error'||result.stopReason==='aborted'){
  // Upstream error bodies can echo request/key data: never print them.
  const status=result.errorMessage?.match(/\b[45]\d\d\b/)?.[0]??'unknown';
  console.error(`FAIL ${id}: ${result.stopReason}, HTTP ${status}; response body withheld`);
  process.exitCode=1;continue;
 }
 assert(events>1);
 assert(result.content.some(p=>p.type==='toolCall' && p.name==='probe' && p.arguments.value==='OK'),`${id}: expected synthetic tool call`);
 console.log(`PASS ${id}: actual work Pi runtime, personal-key exclusion, live streaming/tool parsing through Go proxy`);
}
