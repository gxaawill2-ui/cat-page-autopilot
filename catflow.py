#!/usr/bin/env python3
"""Free, connector-driven Facebook publishing state machine. No tokens stored here."""
import argparse, datetime as dt, hashlib, io, json, re, subprocess, sys, unicodedata, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
PAGE = '1346385028565797'
REPO = 'gxaawill2-ui/cat-page-autopilot'
BASE = 'https://gxaawill2-ui.github.io/cat-page-autopilot/'
TZ = ZoneInfo('Asia/Taipei')

def now(): return dt.datetime.now(TZ).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def norm(s): return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC',s)).strip()
def read(p): return json.loads(Path(p).read_text())
def write(p, data):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp'); temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n'); temp.replace(p)
def git(*args):
    r=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True,text=True)
    if r.returncode: raise RuntimeError('git operation failed: '+args[0]+'; inspect local error privately; do not publish tokens')
    return r.stdout.strip()
def checkpoint(message):
    # The non-forced push is the shared compare-and-swap. A rejected push MUST stop publishing.
    git('add','docs','state','records','CAT-PAGE-STATUS.md')
    if git('diff','--cached','--name-only'):
        git('-c','user.name=cat-page-autopilot','-c','user.email=cat-page-autopilot@users.noreply.github.com','commit','-m',message)
        git('push','origin','HEAD:main')
def sync():
    if git('status','--porcelain'): raise ValueError('Working tree not clean; preserve local work before sync')
    git('pull','--ff-only')
def entries():
    return [read(p) for p in (ROOT/'state/posts').glob('*.json')]
def prepare(args):
    raw=Path(args.image).read_bytes()
    with Image.open(io.BytesIO(raw)) as im:
        im=ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((1600,2000))
        out=io.BytesIO(); im.save(out,'JPEG',quality=90,optimize=True)
        data=out.getvalue(); size=im.size
    if len(data)>4_000_000: raise ValueError('Image exceeds conservative 4MB pipeline limit')
    image_sha=digest(data)
    caption=Path(args.caption).read_text().strip()
    if not caption or len(caption)>63206: raise ValueError('Caption missing or too long')
    key=digest((PAGE+'\n'+norm(caption)+'\n'+image_sha).encode())
    asset='assets/'+image_sha+'.jpg'
    (ROOT/'docs/assets').mkdir(parents=True,exist_ok=True); (ROOT/'docs'/asset).write_bytes(data)
    draft={'key':key,'page_id':PAGE,'caption':caption,'caption_sha256':digest(norm(caption).encode()),'image_sha256':image_sha,'image_url':BASE+asset,'asset_path':'docs/'+asset,'bytes':len(data),'dimensions':list(size),'created_at':now(),'topic':args.topic,'style':args.style,'caption_type':args.caption_type,'source_image':args.source,'sources':args.sources,'status':'draft'}
    write(ROOT/'records/drafts'/f'{key}.json',draft)
    # Human-readable static project art gallery, not a commerce/SaaS host.
    gallery=[]
    for f in sorted((ROOT/'records/drafts').glob('*.json')):
        d=read(f); gallery.append({'key':d['key'],'image_url':d['image_url'],'caption':d['caption'],'topic':d['topic']})
    write(ROOT/'docs/gallery.json',gallery)
    return draft
def url_check(url, expected):
    if not url.startswith(BASE+'assets/') or '?' in url: raise ValueError('Only permanent project HTTPS asset URLs accepted')
    req=urllib.request.Request(url,headers={'User-Agent':'cat-page-image-check/3.0'})
    with urllib.request.urlopen(req,timeout=25) as r:
        b=r.read(4_000_001); result={'url':url,'http_status':r.status,'content_type':r.headers.get('Content-Type'),'bytes':len(b),'sha256':digest(b),'checked_at':now()}
    if result['http_status']!=200 or not result['content_type'].startswith('image/jpeg') or len(b)>4_000_000 or digest(b)!=expected: raise ValueError('Anonymous image GET validation failed: '+json.dumps(result))
    with Image.open(io.BytesIO(b)) as im: im.verify()
    return result
def reserve(args):
    if args.durable: sync()
    d=read(args.draft)
    if d['page_id']!=PAGE: raise ValueError('Wrong Facebook Page')
    policy=read(ROOT/'state/policy.json')
    if policy['mode']!='live' and args.purpose not in ('bootstrap','acceptance'): raise ValueError('DRAFT_GATE: unattended release not accepted')
    if args.purpose=='acceptance' and policy['acceptance_task_id']!=args.task_id: raise ValueError('Unexpected acceptance task')
    for old in entries():
        if old['key']==d['key'] or old['caption_sha256']==d['caption_sha256'] or old['image_sha256']==d['image_sha256']: raise ValueError('DUPLICATE_OR_UNCERTAIN: do not republish same text or image')
        if old['slot']==args.slot: raise ValueError('SLOT_RESERVED: another worker already claimed this slot')
    day=dt.datetime.now(TZ).date().isoformat()
    if not args.slot.startswith(day): raise ValueError('Stale slot cannot publish')
    if sum(x.get('reserved_at','').startswith(day) for x in entries())>=2: raise ValueError('DAILY_LIMIT: two content posts already reserved')
    proof=url_check(d['image_url'],d['image_sha256'])
    d.update(status='publishing',slot=args.slot,reserved_at=now(),purpose=args.purpose,task_id=args.task_id,image_check=proof)
    write(ROOT/'state/posts'/f'{d["key"]}.json',d)
    if args.durable: checkpoint('Reserve Facebook slot '+args.slot)
    return {'key':d['key'],'execute_action':{'connector':'facebook_organic','account':PAGE,'action':'create_photo_post','params':{'image_url':d['image_url'],'caption':d['caption']}},'warning':'Call once ONLY after the durable reserve push succeeds. Unknown outcome stays blocked.'}
def receipt(args):
    p=ROOT/'state/posts'/f'{args.key}.json'; d=read(p)
    if d['status']!='publishing': raise ValueError('Receipt cannot overwrite completed state')
    result=Path(args.result).read_text()
    match=re.search(r'Post id: ('+PAGE+r'_\d+)\.',result)
    if not match: raise ValueError('No genuine post id returned; keep publishing state, reconcile before retry')
    d.update(status='published_unverified',post_id=match[1],published_at=now(),receipt=result)
    write(p,d)
    if args.durable: checkpoint('Save genuine Facebook publication receipt')
    return d
def verify(args):
    p=ROOT/'state/posts'/f'{args.key}.json'; d=read(p); payload=read(args.rows)
    rows=payload.get('data',[]) if isinstance(payload,dict) else payload
    matches=[x for x in rows if x.get('post_id')==d.get('post_id')]
    if len(matches)!=1: raise ValueError('Post not yet in connector readback; do not resend')
    r=matches[0]
    if norm(r.get('post_message',''))!=norm(d['caption']) or not r.get('full_picture'): raise ValueError('Readback text/image mismatch; requires review')
    d.update(status='verified',verified_at=now(),post_url=r['permalink_url'],facebook_created_time=r['post_created_time'],readback={'caption_match':True,'full_picture_present':True,'image_visual_check':args.visual})
    write(p,d)
    if args.durable: checkpoint('Verify Facebook text and image readback')
    return d
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('prepare'); s.add_argument('--image',required=True); s.add_argument('--caption',required=True); s.add_argument('--topic',required=True); s.add_argument('--style',required=True); s.add_argument('--caption-type',default='short_humor'); s.add_argument('--source',required=True); s.add_argument('--sources',nargs='*',default=[])
    s=sub.add_parser('check-url'); s.add_argument('--draft',required=True)
    s=sub.add_parser('checkpoint'); s.add_argument('--message',required=True)
    s=sub.add_parser('reserve'); s.add_argument('--draft',required=True); s.add_argument('--slot',required=True); s.add_argument('--purpose',choices=['bootstrap','acceptance','regular'],default='regular'); s.add_argument('--task-id'); s.add_argument('--durable',action='store_true')
    s=sub.add_parser('receipt'); s.add_argument('--key',required=True); s.add_argument('--result',required=True); s.add_argument('--durable',action='store_true')
    s=sub.add_parser('verify'); s.add_argument('--key',required=True); s.add_argument('--rows',required=True); s.add_argument('--visual',choices=['passed','pending'],default='pending'); s.add_argument('--durable',action='store_true')
    a=p.parse_args()
    if a.cmd=='prepare': result=prepare(a)
    elif a.cmd=='check-url':
        d=read(a.draft); result=url_check(d['image_url'],d['image_sha256']); write(ROOT/'records/url-checks'/f'{d["key"]}.json',result)
    elif a.cmd=='checkpoint': checkpoint(a.message); result={'checkpoint':'pushed','at':now()}
    else: result=globals()[a.cmd](a)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    try: main()
    except Exception as e: print(str(e),file=sys.stderr); sys.exit(1)
