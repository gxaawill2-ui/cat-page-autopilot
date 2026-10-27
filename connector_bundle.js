// Work code-mode binary bridge; returns a bundle for the existing CAS adapter.
// Do not print content/base64. No credentials, no Facebook actions, no retries.
async function loadConnectorBundle(tools, workdir, message, paths) {
 const quote=s=>"'"+s.replace(/'/g,"'\\''")+"'";
 const run=async args=>{
  const r=await tools.exec_command({cmd:'python3 bundle.py '+args.map(quote).join(' '),workdir,max_output_tokens:24000});
  if(r.exit_code!==0||r.session_id)throw Error('Bundle export incomplete; retain draft');
  return JSON.parse(r.output);
 };
 const b=await run(['--manifest',message,...paths]);
 for(const f of b.files){
  if(f.encoding!=='base64')continue;
  const results=await Promise.allSettled(Array.from({length:f.chunk_count},(_,i)=>run(['--chunk',f.path,String(i)])));
  const parts=results.map((r,i)=>{if(r.status!=='fulfilled'||r.value.index!==i)throw Error('Binary chunk failed: '+i);return r.value.part;});
  f.content=parts.join('');
  if(f.content.length!==f.base64_chars||!/^[A-Za-z0-9+/]*={0,2}$/.test(f.content))throw Error('Invalid binary payload');
 }
 return b; // connectorCommit checks expected Git blob SHA before tree/ref CAS.
}
