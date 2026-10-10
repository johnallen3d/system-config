// Exercise the actual TS factory with synthetic Telegram config, without network/model calls.
// node tests/pi-telegram-context-clear.mjs <Pi-runtime> [--installed]
import assert from 'node:assert/strict';
import {createRequire, syncBuiltinESMExports} from 'node:module';
import fs from 'node:fs/promises';
import {homedir} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const runtime=process.argv[2];
assert(runtime, 'Explicit installed Pi runtime required');
const require=createRequire(join(resolve(runtime),'package.json'));
const {createJiti}=require('jiti');
const path=process.argv.includes('--installed')
 ? join(homedir(),'.config/pi/extensions/telegram-context-clear/index.ts')
 : fileURLToPath(new URL('../modules/home-manager/pi/extensions/telegram-context-clear/index.ts',import.meta.url));
const originalRead=fs.readFile;
const originalFetch=globalThis.fetch;
const originalProfile=process.env.PI_CODING_AGENT_DIR;
const originalThreshold=process.env.PI_TELEGRAM_CONTEXT_CLEAR_THRESHOLD;
const configPath=join(homedir(),'.pi/agent/telegram.json');
let reads=0;
let config={botToken:'synthetic-token',allowedUserId:123456};
let requests=[];
let sessions=0;
try {
 fs.readFile=async(path,...args)=>{
  if(path!==configPath) return originalRead(path,...args);
  reads++;
  if(config instanceof Error) throw config;
  return JSON.stringify(config);
 };
 syncBuiltinESMExports();
 globalThis.fetch=async(url,options)=>{
  requests.push({url,body:JSON.parse(options.body)});
  return {json:async()=>({ok:true})};
 };
 process.env.PI_CODING_AGENT_DIR=join(homedir(),'.config/pi');
 process.env.PI_TELEGRAM_CONTEXT_CLEAR_THRESHOLD='0';
 const jiti=createJiti(import.meta.url,{moduleCache:false});
 const factory=(await jiti.import(path)).default;
 const hooks=new Map();
 factory({on:(name,handler)=>hooks.set(name,handler)});
 const ctx={
  newSession:async()=>{sessions++;},
  getContextUsage:()=>{throw Error('Manual-only extension must not inspect context usage');},
 };
 assert.deepEqual([...hooks.keys()],['input'],'Only manual input handling should remain');
 // Replay lifecycle boundaries even with a legacy threshold of zero.
 for(const percent of [0,69,70,82.2,99,100]) {
  for(const name of ['session_start','agent_end','session_compact']) {
   await hooks.get(name)?.({}, {...ctx,getContextUsage:()=>({percent})});
  }
 }
 assert.equal(reads,0);assert.equal(requests.length,0);assert.equal(sessions,0);
 const input=hooks.get('input');
 for(const source of ['interactive','rpc']) {
  assert.deepEqual(await input({source,text:'[telegram] /clear-context'},ctx),{action:'continue'});
 }
 for(const text of ['hello','/clear-context','[telegram] /clear-context please']) {
  assert.deepEqual(await input({source:'extension',text},ctx),{action:'continue'});
 }
 assert.equal(reads,0);
 process.env.PI_CODING_AGENT_DIR=join(homedir(),'.config/pi-work');
 assert.deepEqual(await input({source:'extension',text:'[telegram] /clear-context'},ctx),{action:'continue'});
 assert.equal(reads,0);
 process.env.PI_CODING_AGENT_DIR=join(homedir(),'.config/pi');
 assert.deepEqual(await input({source:'extension',text:' [telegram] /clear-context '},ctx),{action:'handled'});
 assert.equal(sessions,1);assert.equal(reads,1);
 assert.deepEqual(requests,[{
  url:'https://api.telegram.org/botsynthetic-token/sendMessage',
  body:{chat_id:123456,text:'Pi session cleared.'},
 }]);
 // Missing config still permits explicitly requested clearing, without a notification.
 config=new Error('Synthetic missing Telegram config');requests=[];
 await input({source:'extension',text:'[telegram] /clear-context'},ctx);
 assert.equal(sessions,2);assert.equal(requests.length,0);
 // Preserve existing network-error propagation after the session has been cleared.
 config={botToken:'synthetic-token',allowedUserId:123456};
 globalThis.fetch=async()=>{throw Error('Synthetic network failure');};
 await assert.rejects(input({source:'extension',text:'[telegram] /clear-context'},ctx),/Synthetic network failure/);
 assert.equal(sessions,3);
 console.log('PASS no automatic alerts at any usage, manual Telegram clearing, exact command/source guards, work-profile isolation, missing config and network-error behavior');
} finally {
 fs.readFile=originalRead;
 syncBuiltinESMExports();
 globalThis.fetch=originalFetch;
 if(originalProfile===undefined) delete process.env.PI_CODING_AGENT_DIR;
 else process.env.PI_CODING_AGENT_DIR=originalProfile;
 if(originalThreshold===undefined) delete process.env.PI_TELEGRAM_CONTEXT_CLEAR_THRESHOLD;
 else process.env.PI_TELEGRAM_CONTEXT_CLEAR_THRESHOLD=originalThreshold;
}
