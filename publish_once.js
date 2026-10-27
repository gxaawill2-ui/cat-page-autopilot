// Run only in Work code mode. bundle CAS parent/tree must be current. No credentials.
// caller supplies the reserved state file bundle and an armed state produced by dispatch_guard.arm.
async function publishOnce(tools, bundle, armed, connectorCommit) {
 if(typeof tools.mcp__codex_apps__windsor_ai_execute_action!=='function')throw Error('WINDSOR_TOOL_UNAVAILABLE_BEFORE_CAS: no dispatch attempted');
 if(armed.status!=='publishing'||armed.dispatch_protocol!==2||!armed.dispatch_nonce||!armed.dispatch_owner||!armed.dispatch_started_at)throw Error('Missing armed dispatch fence');
 const file=bundle.files.find(x=>x.path==='state/posts/'+armed.key+'.json');
 if(!file||file.encoding==='base64'||JSON.stringify(JSON.parse(file.content))!==JSON.stringify(armed))throw Error('CAS bundle does not match armed intent');
 const saved=await connectorCommit(tools,bundle); // CAS loser throws BEFORE any Facebook call
 if(saved.success!==true)throw Error('CAS not committed');
 // No retry: a crash/timeout after CAS must be externally reconciled, never replayed.
 const result=await tools.mcp__codex_apps__windsor_ai_execute_action({connector:'facebook_organic',account:'1346385028565797',action:'create_photo_post',params:{image_url:armed.image_url,caption:armed.caption}});
 return {saved,result}; // save genuine receipt immediately; unknown return leaves fence intact
}
