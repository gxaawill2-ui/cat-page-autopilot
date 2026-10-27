// Called from Work code mode, with its supplied tools object. Never expose credentials.
// bundle={parent,baseTree,message,files:[{path,content,encoding:'utf-8'|'base64'}]}
// Parent and baseTree must come from the SAME fresh checkout, never guessed.
async function connectorCommit(tools, bundle) {
  const repository_full_name='gxaawill2-ui/cat-page-autopilot';
  const ok=r=>{if(r.isError)throw Error(JSON.stringify(r));return r.structuredContent};
  const tree_elements=[];
  for(const f of bundle.files){
    if(f.path.startsWith('/')||f.path.split('/').includes('..')||/(^|\/)(\.env|private)(\/|$)/.test(f.path))throw Error('Unsafe path');
    const b=ok(await tools.mcp__codex_apps__github_create_blob({repository_full_name,content:f.content,encoding:f.encoding||'utf-8'}));
    if(!b.sha)throw Error('Blob receipt missing');
    if(f.expected_blob_sha && b.sha!==f.expected_blob_sha)throw Error('Binary blob SHA mismatch; do not create tree or publish');
    tree_elements.push({path:f.path,mode:'100644',type:'blob',sha:b.sha});
  }
  const tree=ok(await tools.mcp__codex_apps__github_create_tree({repository_full_name,base_tree_sha:bundle.baseTree,tree_elements}));
  const c=ok(await tools.mcp__codex_apps__github_create_commit({repository_full_name,parent_sha:bundle.parent,tree_sha:tree.sha,message:bundle.message}));
  const ref=ok(await tools.mcp__codex_apps__github_update_ref({repository_full_name,branch_name:'main',sha:c.sha,expected_sha:bundle.parent,force:false}));
  if(ref.success!==true)throw Error('CAS failed; do not publish, resync and re-evaluate duplicates');
  return {sha:c.sha,tree:tree.sha,success:true};
}
