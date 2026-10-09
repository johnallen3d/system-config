// Installed Pi 1.x audit and native MCP smoke tests, without model calls.
// PI_CODING_AGENT_DIR=<profile> node tests/pi-native-personal.mjs <runtime-root> [--live]
import assert from 'node:assert/strict';
import {readFile, access} from 'node:fs/promises';
import {createServer} from 'node:http';
import {homedir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const profile=process.env.PI_CODING_AGENT_DIR;
assert(root && profile, 'Explicit installed runtime and PI_CODING_AGENT_DIR required');
const personal=profile===join(homedir(),'.config/pi');
assert(personal || profile===join(homedir(),'.config/pi-work'));
const imp=p=>import(pathToFileURL(join(root,'dist',p)).href);
const {DefaultResourceLoader}=await imp('core/resource-loader.js');
const {SettingsManager}=await imp('core/settings-manager.js');
const {DefaultPackageManager}=await imp('core/package-manager.js');
const {builtInExtensions}=await imp('extensions/index.js');
const {loadMcpConfig}=await imp('extensions/mcp/config.js');
const nativeConfig=personal ? loadMcpConfig({agentDir:profile,cwd:process.cwd(),projectTrusted:false}) : undefined;
if(personal){
 assert.deepEqual(nativeConfig.errors,[],'Installed native MCP config must validate');
 assert(!nativeConfig.servers.some(s=>s.name==='cloudflare-api'),'Cloudflare is work-only');
 assert(nativeConfig.servers.every(s=>!s.config.exposure || s.config.exposure==='codemode'));
}
const settings=SettingsManager.create(process.cwd(),profile);
const loader=new DefaultResourceLoader({cwd:process.cwd(),agentDir:profile,settingsManager:settings,extensionFactories:builtInExtensions});
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const paths=loader.getExtensions().extensions.map(e=>e.path);
const hasWorkKit=paths.some(p=>p.includes('/agent-kit/'));
if(personal){
 assert(paths.includes('builtin:mcp'),JSON.stringify(paths));
 assert(!paths.some(p=>p.includes('/pi-mcp-adapter/')));
 assert(!settings.getGlobalSettings().extensions?.includes('-builtin:mcp'));
 assert.equal(loader.getSystemPrompt(),undefined,'Personal instructions must not replace native prompt');
 assert(loader.getAppendSystemPrompt().some(p=>p.includes('$PI_CODING_AGENT_DIR')));
 await assert.rejects(access(join(profile,'mcp-adapter.json')));
 const packages=settings.getGlobalSettings().packages;
 assert.deepEqual(packages,['npm:pi-headroom','npm:pi-prompt-template-model','npm:pi-web-search']);
 const deps=JSON.parse(await readFile(join(profile,'npm/package.json'),'utf8')).dependencies;
 assert.deepEqual(Object.keys(deps).sort(),packages.map(p=>p.slice(4)).sort(),'Stale direct dependencies remain');
 assert(loader.getPrompts().prompts.some(p=>p.name==='wrap'));
 assert(paths.some(p=>p.includes('/pi-prompt-template-model/')));
 const manager=new DefaultPackageManager({cwd:process.cwd(),agentDir:profile,settingsManager:settings});
 const updates=await manager.checkForAvailableUpdates();
 assert(!updates.some(u=>u.source==='npm:pi-mcp-adapter'));
 console.log('PASS personal native MCP, default prompt, retained template features, exact package ownership; adapter update notice absent');
}else{
 assert(hasWorkKit,'Work agent-kit must still load');
 assert(settings.getGlobalSettings().packages.includes('git:github.com/amfaro/agent-kit'));
 assert.equal(loader.getSystemPrompt(),await readFile(join(profile,'SYSTEM.md'),'utf8'));
 console.log('PASS work agent-kit and existing work prompt retained; no extension-load errors');
}
console.log('LOADED',JSON.stringify(paths));
const {McpServerConnection,createDefaultTransport,McpOAuthCredentialStore}=await imp('extensions/mcp/runtime.js');
const {InMemoryAuthStorageBackend}=await imp('core/auth-storage.js');
const credentials=new McpOAuthCredentialStore(new InMemoryAuthStorageBackend());
let calls=0;
const server=createServer(async(req,res)=>{
 if(req.headers.authorization!=='Bearer synthetic-personal-token'){
  res.writeHead(401,{'www-authenticate':'Bearer','content-type':'application/json'});
  return res.end(JSON.stringify({error:'sign-in required'}));
 }
 if(req.method!=='POST'){res.writeHead(405);return res.end();}
 let body='';for await(const chunk of req)body+=chunk;
 const message=JSON.parse(body);
 if(message.id===undefined){res.writeHead(202);return res.end();}
 let result;
 if(message.method==='initialize')result={protocolVersion:'2025-11-25',capabilities:{tools:{}},serverInfo:{name:'native-fixture',version:'1'}};
 else if(message.method==='tools/list')result={tools:[{name:'echo',description:'Synthetic read-only fixture',inputSchema:{type:'object',properties:{text:{type:'string'}},required:['text']},annotations:{readOnlyHint:true}}]};
 else if(message.method==='tools/call'){calls++;result={content:[{type:'text',text:message.params.arguments.text}]};}
 else throw Error(`Unexpected fixture method ${message.method}`);
 res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify({jsonrpc:'2.0',id:message.id,result}));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const url=`http://127.0.0.1:${server.address().port}/mcp`;
await credentials.forServer('fixture',url).save({serverUrl:url,tokens:{access_token:'synthetic-personal-token',token_type:'Bearer'},tokensExpireAt:Date.now()+3600000});
const connection=(name,config)=>new McpServerConnection({entry:{name,config,source:'synthetic fixture',scope:'extension'},cwd:process.cwd(),createTransport:createDefaultTransport,credentials,onTools:()=>{}});
const authorized=connection('fixture',{url});
const isolated=connection('other-profile',{url});
try{
 await authorized.getClient();
 assert.equal(authorized.state,'connected');
 assert.equal(authorized.tools.length,1);
 assert.equal(authorized.tools[0].annotations.readOnlyHint,true);
 const result=await authorized.callTool('echo',{text:'OK'},{});
 assert.equal(result.content[0].text,'OK');assert.equal(calls,1);
 await assert.rejects(isolated.getClient());assert.equal(isolated.state,'needs-auth');
 assert.equal(credentials.forServer('fixture',url+'/other').load(),undefined);
 console.log('PASS native HTTP lifecycle, stored OAuth token, tool call, annotations, server-name/URL credential isolation');
}finally{
 await Promise.all([authorized.close(),isolated.close()]);
 server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
}
if(personal && process.argv.includes('--live')){
 const liveCredentials=new McpOAuthCredentialStore();
 for(const entry of nativeConfig.servers){
  const {name,config:definition}=entry;
  const c=new McpServerConnection({entry:{name,config:definition,source:join(profile,'mcp.json'),scope:'global'},cwd:process.cwd(),createTransport:createDefaultTransport,credentials:liveCredentials,onTools:()=>{}});
  try{
   await c.getClient();
   assert.equal(c.state,'connected');
   let tool,args;
   if(name==='mcp-server-motherduck'){tool='execute_query';args={sql:'SELECT 1 AS pi_native_smoke'};}
   if(name==='headroom'){tool='headroom_stats';args={};}
   if(name==='mcp-server-doppler' && (process.platform==='darwin' || process.env.DOPPLER_TOKEN)){tool='auth_me';args={};}
   if(tool){const result=await c.callTool(tool,args,{});assert(!result.isError,`${name}: read-only smoke failed`);}
   console.log(`PASS live ${name}: ${c.tools.length} tools${tool?', read-only call succeeded':''}`);
  }catch(error){
   // #694 owns the pre-existing service-account approvals on each host.
   if(name==='cloudflare-api' && c.state==='needs-auth') console.log('PRE-EXISTING: Cloudflare requires browser approval (adapter baseline also needs-auth)');
   else if(name==='mcp-server-doppler' && !process.env.DOPPLER_TOKEN) console.log(`PRE-EXISTING: Doppler token unavailable in this host environment (#694): ${c.state}`);
   else throw error;
  }finally{await c.close();}
 }
}
process.exit(0);
