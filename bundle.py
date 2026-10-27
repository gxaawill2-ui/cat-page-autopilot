#!/usr/bin/env python3
"""Read-only export for connector_commit.js. Do not print its binary output to the chat."""
import base64,json,subprocess,sys,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def git(*a): return subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
CHUNK_CHARS=24000
def checked(p):
    path=Path(p)
    if path.is_absolute() or '..' in path.parts: raise SystemExit('Unsafe path')
    return path
if len(sys.argv)>1 and sys.argv[1]=='--chunk':
    path=checked(sys.argv[2]); index=int(sys.argv[3]); b=(ROOT/path).read_bytes(); data=base64.b64encode(b).decode()
    if index<0 or index*CHUNK_CHARS>=len(data): raise SystemExit('Invalid chunk index')
    print(json.dumps({'index':index,'part':data[index*CHUNK_CHARS:(index+1)*CHUNK_CHARS]})); raise SystemExit(0)
manifest=len(sys.argv)>1 and sys.argv[1]=='--manifest'
if manifest: sys.argv.pop(1)
if len(sys.argv)<3: raise SystemExit('bundle.py MESSAGE PATH [PATH...]')
parent=git('rev-parse','origin/main'); tree=git('rev-parse','origin/main^{tree}')
files=[]
for p in sys.argv[2:]:
    path=Path(p)
    if path.is_absolute() or '..' in path.parts: raise SystemExit('Unsafe path')
    b=(ROOT/path).read_bytes()
    if path.suffix in ('.json','.py','.js','.md','.yml','.yaml','.txt'):
        files.append({'path':p,'content':b.decode('utf-8'),'encoding':'utf-8'})
    else:
        data=base64.b64encode(b).decode()
        f={'path':p,'encoding':'base64','expected_blob_sha':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()}
        if manifest: f.update(base64_chars=len(data),chunk_count=math.ceil(len(data)/CHUNK_CHARS),chunk_chars=CHUNK_CHARS,sha256=hashlib.sha256(b).hexdigest())
        else: f['content']=data
        files.append(f)
print(json.dumps({'parent':parent,'baseTree':tree,'message':sys.argv[1],'files':files}))
