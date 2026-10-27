const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto'),cp=require('child_process');
const context={};vm.createContext(context);
vm.runInContext(fs.readFileSync('connector_bundle.js','utf8')+'\n'+fs.readFileSync('connector_commit.js','utf8'),context);
(async()=>{
 const path='docs/assets/8bbd66eccbb16d879b435afa21e691e210dc0d850ca0310538ff8ad0a61e1b23.jpg';
 const binary=fs.readFileSync(path);let trees=0,calls=0;
 const tools={exec_command:async o=>({exit_code:0,output:cp.execSync(o.cmd,{cwd:o.workdir,encoding:'utf8',maxBuffer:2e6})}),
 mcp__codex_apps__github_create_blob:async o=>{calls++;const data=Buffer.from(o.content,o.encoding==='base64'?'base64':'utf8');return {structuredContent:{sha:crypto.createHash('sha1').update(Buffer.concat([Buffer.from('blob '+data.length+'\0'),data])).digest('hex')}}},
 mcp__codex_apps__github_create_tree:async()=>{trees++;return {structuredContent:{sha:'tree'}}},
 mcp__codex_apps__github_create_commit:async()=>({structuredContent:{sha:'commit'}}),mcp__codex_apps__github_update_ref:async()=>({structuredContent:{success:true}})};
 const b=await context.loadConnectorBundle(tools,process.cwd(),'binary bridge test',[path]);
 assert(Buffer.from(b.files[0].content,'base64').equals(binary));assert(b.files[0].chunk_count>1);
 assert((await context.connectorCommit(tools,b)).success);assert.equal(trees,1);
 b.files[0].expected_blob_sha='bad';await assert.rejects(context.connectorCommit(tools,b),/Binary blob SHA mismatch/);assert.equal(trees,1);
 console.log('Real JPEG multi-chunk roundtrip and Git blob SHA gate: PASS; GitHub mocked, Facebook calls zero');
})().catch(e=>{console.error(e);process.exitCode=1});
