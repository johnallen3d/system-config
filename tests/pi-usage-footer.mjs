// Actual TS factory/render tests; no model calls or real OAuth credentials.
// PI_CODING_AGENT_DIR=<personal> node tests/pi-usage-footer.mjs <Pi-runtime> [--installed] [--live]
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdtempSync, writeFileSync, rmSync, readFileSync} from 'node:fs';
import {homedir, tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {promisify} from 'node:util';
import {execFile} from 'node:child_process';
const runtime=process.argv[2];
assert(runtime, 'Explicit installed Pi runtime required');
const require=createRequire(join(resolve(runtime),'package.json'));
const {createJiti}=require('jiti');
const {visibleWidth}=await import(require.resolve('@earendil-works/pi-tui'));
const jiti=createJiti(import.meta.url,{moduleCache:false,alias:{
 '@mariozechner/pi-tui':require.resolve('@earendil-works/pi-tui'),
}});
const path=process.argv.includes('--installed') ? join(homedir(),'.config/pi/extensions/usage-footer/index.ts')
 : resolve('modules/home-manager/pi/extensions/usage-footer/index.ts');
const factory=(await jiti.import(path)).default;
const originalProfile=process.env.PI_CODING_AGENT_DIR;
const originalFetch=globalThis.fetch;
const temp=mkdtempSync(join(tmpdir(),'pi-footer-'));
const theme={fg:(_color,text)=>text};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const quota={plan_type:'pro',rate_limit:{
 primary_window:{used_percent:23,limit_window_seconds:18000,reset_at:1791989283},
 secondary_window:{used_percent:47,limit_window_seconds:604800,reset_at:1791989283},
}};
const hooks=new Map();let footer;let calls=[];let response=quota;let failure=false;let pending;
const pi={on:(name,handler)=>hooks.set(name,handler),exec:async(command,args,options)=>{
 calls.push({command,args,options});
 if(pending) await pending;
 return failure ? {code:1,killed:false,stdout:'',stderr:'secret-sentinel'}
 : {code:0,killed:false,stdout:JSON.stringify(response),stderr:''};
}};
factory(pi);
const ctx={mode:'tui',model:{provider:'subscription-codex',id:'gpt-6.1-sol',baseUrl:'http://100.97.112.40:8317/v1'},
 sessionManager:{getEntries:()=>[]},getContextUsage:()=>({tokens:1000,contextWindow:200000,percent:0.5}),
 ui:{setFooter:fn=>{footer?.dispose();footer=fn({requestRender:()=>{}},theme,{onBranchChange:()=>()=>{}});}},
};
try{
 process.env.PI_CODING_AGENT_DIR=join(homedir(),'.config/pi');
 globalThis.fetch=()=>{throw Error('Proxy quota must not use local OAuth');};
 hooks.get('session_start')({},ctx);await settle();
 assert.deepEqual(calls[0].args,['codex-usage','personal','--base-url',ctx.model.baseUrl]);
 assert.equal(calls[0].command,'subscription-proxy');
 assert(calls[0].options.timeout>0);
 let line=footer.render(200).join('\n');
 assert.match(line,/5h 23%.*7d 47%/);assert.doesNotMatch(line,/\$0\.000 session/);
 const count=calls.length;footer.render(200);await settle();assert.equal(calls.length,count,'Poll throttled');
 for(const width of [20,40,80,200]) assert(footer.render(width).every(l=>visibleWidth(l)<=width));
 response={plan_type:'prolite',rate_limit:{primary_window:quota.rate_limit.secondary_window,secondary_window:null}};
 hooks.get('agent_end')({},ctx);await settle();
 line=footer.render(200).join('\n');assert.match(line,/7d 47%/);assert.doesNotMatch(line,/5h/);
 failure=true;hooks.get('agent_end')({},ctx);await settle();
 line=footer.render(200).join('\n');assert.match(line,/gateway quota unavailable/);
 assert.doesNotMatch(line,/secret-sentinel|\$0\.000 session/);
 failure=false;response=quota;
 let release;pending=new Promise(resolve=>{release=resolve;});
 hooks.get('agent_end')({},ctx);hooks.get('agent_end')({},ctx);footer.render(200);
 const inFlightCount=calls.length;await settle();assert.equal(calls.length,inFlightCount);
 release();pending=undefined;await settle();
 // Profile and gateway changes cannot reuse another source's cached quota.
 process.env.PI_CODING_AGENT_DIR=join(homedir(),'.config/pi-work');
 ctx.model={...ctx.model,baseUrl:'http://100.97.112.40:8318/v1'};
 assert.doesNotMatch(footer.render(200).join('\n'),/23%|47%/);await settle();
 assert.equal(calls.at(-1).args[1],'work');
 process.env.PI_CODING_AGENT_DIR=temp;
 hooks.get('agent_end')({},ctx);await settle();
 assert.match(footer.render(200).join('\n'),/unsupported proxy profile/);
 // Native Codex remains supported, using only the synthetic active credential.
 writeFileSync(join(temp,'auth.json'),JSON.stringify({'openai-codex':{type:'oauth',access:'synthetic-token',accountId:'synthetic-account'}}));
 let nativeCalls=0;
 globalThis.fetch=async(_url,options)=>{
  nativeCalls++;assert.equal(options.headers.Authorization,'Bearer synthetic-token');
  assert.equal(options.headers['ChatGPT-Account-Id'],'synthetic-account');
  assert(options.signal);return {ok:true,json:async()=>quota};
 };
 ctx.model={provider:'openai-codex',id:'test',baseUrl:'https://chatgpt.com/backend-api'};
 hooks.get('agent_end')({},ctx);await settle();
 assert.equal(nativeCalls,1);assert.match(footer.render(200).join('\n'),/5h 23%.*7d 47%/);
 ctx.model={provider:'unrelated',id:'test'};
 assert.match(footer.render(200).join('\n'),/usage: \$0\.000 session/);
 const before=calls.length;hooks.get('session_start')({},{...ctx,mode:'rpc'});
 await settle();assert.equal(calls.length,before,'Non-TUI loading does not query quota');
 console.log('PASS quota provider routing, percentages/reset times, actual windows, errors, source isolation, bounded polling, narrow rendering, native Codex, non-TUI guard');
 if(process.argv.includes('--live')){
  assert.equal(originalProfile,join(homedir(),'.config/pi'),'Live probe requires explicit personal profile');
  process.env.PI_CODING_AGENT_DIR=originalProfile;
  const model=JSON.parse(readFileSync(join(originalProfile,'models.json'),'utf8')).providers['subscription-codex'];
  ctx.model={provider:'subscription-codex',id:model.models[0].id,baseUrl:model.baseUrl};
  let liveRequest;
  pi.exec=(command,args)=>liveRequest=promisify(execFile)(command,args,{timeout:35000})
   .then(({stdout})=>({code:0,killed:false,stdout}));
  hooks.get('agent_end')({},ctx);assert(liveRequest);await liveRequest;await settle();
  const lines=footer.render(200).join('\n');
  assert.match(lines,/(?:5h|7d) \d+%/);assert.doesNotMatch(lines,/\$0\.000 session/);
  console.log('PASS live installed footer:',lines);
 }
}finally{
 footer?.dispose();globalThis.fetch=originalFetch;
 if(originalProfile===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=originalProfile;
 rmSync(temp,{recursive:true,force:true});
}
