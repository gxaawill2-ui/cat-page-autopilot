const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('publish_once.js','utf8'),ctx);
(async()=>{let head='base',calls=0;const cas=async(_,b)=>{if(b.parent!==head)throw Error('CAS conflict');head='new';return {success:true}};
const armed={key:'x',status:'publishing',dispatch_protocol:2,dispatch_nonce:'n',dispatch_owner:'r',dispatch_started_at:'now',image_url:'u',caption:'c'};
const bundle={parent:'base',files:[{path:'state/posts/x.json',content:JSON.stringify(armed)}]};
const tools={mcp__codex_apps__windsor_ai_execute_action:async()=>{calls++;throw Error('response unknown')}};
const results=await Promise.allSettled([ctx.publishOnce(tools,bundle,armed,cas),ctx.publishOnce(tools,bundle,armed,cas)]);assert.equal(calls,1);assert(results.every(r=>r.status==='rejected'));
await assert.rejects(ctx.publishOnce(tools,bundle,armed,cas));assert.equal(calls,1);console.log('Concurrent CAS loser, unknown response, replay: PASS; Facebook calls simulated only');})();
