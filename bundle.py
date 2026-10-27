#!/usr/bin/env python3
"""Read-only export for connector_commit.js. Do not print its binary output to the chat."""
import base64,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def git(*a): return subprocess.check_output(['git','-C',str(ROOT),*a],text=True).strip()
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
        files.append({'path':p,'content':base64.b64encode(b).decode(),'encoding':'base64'})
print(json.dumps({'parent':parent,'baseTree':tree,'message':sys.argv[1],'files':files}))
