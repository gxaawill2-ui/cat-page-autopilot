"""Anonymous Pages verifier; only repository hash-named JPEG assets, no secrets."""
import datetime as dt, hashlib, json, os, pathlib, urllib.request
BASE='https://gxaawill2-ui.github.io/cat-page-autopilot/'
def probe(d):
    sha=d['image_sha256']; assert len(sha)==64 and all(c in '0123456789abcdef' for c in sha)
    url=BASE+'assets/'+sha+'.jpg'; assert d['image_url']==url
    with urllib.request.urlopen(url,timeout=25) as r:
        b=r.read(4000001); mime=r.headers.get_content_type(); status=r.status
        assert r.url==url, 'redirect rejected'
    assert status==200 and mime=='image/jpeg' and len(b)<=4000000
    assert b[:2]==b'\xff\xd8' and b[-2:]==b'\xff\xd9'
    assert hashlib.sha256(b).hexdigest()==sha
    assert pathlib.Path('docs/assets/'+sha+'.jpg').read_bytes()==b
    return dict(url=url,http_status=status,content_type=mime,bytes=len(b),sha256=sha,checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),validator='github-actions-pages-probe',run_id=os.environ['GITHUB_RUN_ID'],source_commit=os.environ['GITHUB_SHA'])
if __name__=='__main__':
    for p in pathlib.Path('records/drafts').glob('*.json'):
        d=json.loads(p.read_text()); out=pathlib.Path('records/pages-proofs')/(d['key']+'.json')
        try:
            result=probe(d);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
        except Exception as e: print(json.dumps({'draft':p.name,'failed':str(e)}),flush=True);raise
