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
    raise ValueError('Use the connected GitHub adapter in connector_commit.js; terminal push is unauthenticated. Never publish before its successful CAS receipt.')
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
    draft={'key':key,'page_id':PAGE,'caption':caption,'caption_sha256':digest(norm(caption).encode()),'image_sha256':image_sha,'image_url':BASE+asset,'asset_path':'docs/'+asset,'bytes':len(data),'dimensions':list(size),'created_at':now(),'topic':args.topic,'style':args.style,'caption_type':args.caption_type,'source_image':args.source,'sources':args.sources,'status':'draft','language':getattr(args,'language',None),'target_markets':getattr(args,'target_markets',[]),'experiment_id':getattr(args,'experiment_id',None)}
    write(ROOT/'records/drafts'/f'{key}.json',draft)
    # Human-readable static project art gallery, not a commerce/SaaS host.
    gallery=[]
    for f in sorted((ROOT/'records/drafts').glob('*.json')):
        d=read(f)
        if not all(d.get(k) for k in ('key','image_url','caption','topic')):
            continue  # Recovery checkpoints can precede asset preparation.
        gallery.append({k:d[k] for k in ('key','image_url','caption','topic')})
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
def release_check(d):
    try:
        return url_check(d['image_url'],d['image_sha256'])
    except urllib.error.HTTPError:
        raise  # real HTTP failure is never replaced by stale evidence
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        proof=read(ROOT/'records/pages-proofs'/f'{d["key"]}.json')
        age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(proof['checked_at'])).total_seconds()
        if not (0 <= age <= 3600 and proof.get('validator')=='github-actions-pages-probe' and proof.get('run_id') and re.fullmatch(r'[0-9a-f]{40}',proof.get('source_commit','')) and proof['url']==d['image_url'] and proof['sha256']==d['image_sha256'] and proof['http_status']==200 and proof['content_type']=='image/jpeg'):
            raise ValueError('No fresh matching Actions Pages evidence') from exc
        if digest((ROOT/d['asset_path']).read_bytes())!=proof['sha256']:
            raise ValueError('Local asset differs from verified Pages bytes')
        return proof

def quarantined_historical_pending(old, new_slot):
    """Only one explicitly allowlisted historical UNKNOWN may cease blocking OTHER content.
    This never resolves, deletes, retries, or changes the historical record.
    Current-day, protocol2, non-allowlisted and mismatching records still block.
    """
    if old.get('status')!='publishing' or old.get('dispatch_protocol') not in (None,1):
        return False
    r=old.get('reconciliation') or {}
    if r.get('classification')!='unknown' or r.get('closure_allowed') is not False or r.get('resend_allowed') is not False:
        return False
    try:
        q=read(ROOT/'state/legacy_quarantine.json')
    except (FileNotFoundError, ValueError, OSError):
        return False
    if not(q.get('enabled') is True and q.get('mode')=='scoped_legacy_quarantine'):
        return False
    for item in q.get('quarantined',[]):
        identity=('key','slot','caption_sha256','image_sha256')
        if not all(item.get(k) and item[k]==old.get(k) for k in identity):
            continue
        if item.get('status')!='unknown_not_closed' or item.get('resend_allowed') is not False:
            continue
        if item.get('evidence_record')!=r.get('evidence_record'):
            continue
        try:
            old_day=dt.datetime.fromisoformat(old['slot']).date()
            new_day=dt.datetime.fromisoformat(new_slot).date()
        except (ValueError, TypeError):
            return False
        if old_day < new_day:
            return True
    return False

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
    if dt.datetime.fromisoformat(args.slot).date().isoformat()!=day: raise ValueError('Stale slot cannot publish')
    if sum(dt.datetime.fromisoformat(x['reserved_at']).astimezone(TZ).date().isoformat()==day for x in entries() if x.get('reserved_at'))>=policy.get('daily_limit',2): raise ValueError('DAILY_LIMIT: configured daily content cap reached')
    if any(x.get('status') in ('reserved','publishing','published_unverified') and not quarantined_historical_pending(x,args.slot) for x in entries()): raise ValueError('UNRESOLVED_PUBLICATION: reconcile unknown non-quarantined post before release')
    if args.purpose=='regular':
        from international import plan
        expected=plan(args.slot)
        if d.get('language')!=expected['language'] or d.get('target_markets')!=expected['target_markets'] or d.get('experiment_id')!=expected['experiment_id']: raise ValueError('INTERNATIONAL_METADATA_MISMATCH')
    proof=release_check(d)
    d.update(status='reserved' if args.purpose=='regular' else 'publishing',dispatch_protocol=2 if args.purpose=='regular' else 1,slot=args.slot,reserved_at=now(),purpose=args.purpose,task_id=args.task_id,image_check=proof)
    write(ROOT/'state/posts'/f'{d["key"]}.json',d)
    if args.durable: checkpoint('Reserve Facebook slot '+args.slot)
    return {'key':d['key'],'execute_action':{'connector':'facebook_organic','account':PAGE,'action':'create_photo_post','params':{'image_url':d['image_url'],'caption':d['caption']}},'warning':'REGULAR MUST ARM: CAS-save reserved first; dispatch_guard.arm then CAS-save publishing with unique owner/nonce; ONLY winning CAS caller may invoke Windsor once; never resume/replay publishing. LOCAL_INTENT_ONLY: use connector_commit.js to save this state with expected parent SHA; call once ONLY after CAS success. Unknown outcome stays blocked.'}
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
    if args.visual!='passed': raise ValueError('Visual verification required before clearing publication lock')
    if norm(r.get('post_message',''))!=norm(d['caption']) or not r.get('full_picture'): raise ValueError('Readback text/image mismatch; requires review')
    d.update(status='verified',verified_at=now(),post_url=r['permalink_url'],facebook_created_time=r['post_created_time'],readback={'caption_match':True,'full_picture_present':True,'image_visual_check':args.visual})
    write(p,d)
    if args.durable: checkpoint('Verify Facebook text and image readback')
    return d
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('prepare'); s.add_argument('--image',required=True); s.add_argument('--caption',required=True); s.add_argument('--topic',required=True); s.add_argument('--style',required=True); s.add_argument('--caption-type',default='short_humor'); s.add_argument('--source',required=True); s.add_argument('--sources',nargs='*',default=[])
    s.add_argument('--language',choices=['en','ja','zh-Hant']); s.add_argument('--target-markets',nargs='*',default=[]); s.add_argument('--experiment-id')
    s=sub.add_parser('check-url'); s.add_argument('--draft',required=True)
    s=sub.add_parser('checkpoint'); s.add_argument('--message',required=True)
    s=sub.add_parser('reserve'); s.add_argument('--draft',required=True); s.add_argument('--slot',required=True); s.add_argument('--purpose',choices=['bootstrap','acceptance','regular'],default='regular'); s.add_argument('--task-id'); s.add_argument('--durable',action='store_true')
    s=sub.add_parser('receipt'); s.add_argument('--key',required=True); s.add_argument('--result',required=True); s.add_argument('--durable',action='store_true')
    s=sub.add_parser('verify'); s.add_argument('--key',required=True); s.add_argument('--rows',required=True); s.add_argument('--visual',choices=['passed','pending'],default='pending'); s.add_argument('--durable',action='store_true')
    a=p.parse_args()
    if a.cmd=='prepare': result=prepare(a)
    elif a.cmd=='check-url':
        d=read(a.draft); result=release_check(d); write(ROOT/'records/url-checks'/f'{d["key"]}.json',result)
    elif a.cmd=='checkpoint': checkpoint(a.message); result={'checkpoint':'pushed','at':now()}
    else: result=globals()[a.cmd](a)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    try: main()
    except Exception as e: print(str(e),file=sys.stderr); sys.exit(1)
