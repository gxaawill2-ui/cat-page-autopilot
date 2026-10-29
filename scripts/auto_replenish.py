#!/usr/bin/env python3
"""Prepare AI-original future cat posts and submit them once to Meta native scheduler.
Fail closed; never post immediately and never replay uncertain writes.
"""
import base64, datetime as dt, hashlib, io, json, os, re, subprocess, sys
import urllib.request, urllib.error
from pathlib import Path
from PIL import Image, ImageOps
import meta_native_schedule as native
import meta_graph_publish as base

ROOT=base.ROOT
TZ=base.TZ
SLOTS=("09:30","12:30","16:30","19:30")
GATEWAY="https://ai-gateway.vercel.sh/v1"
TEXT=os.environ.get("AUTOPILOT_TEXT_MODEL","nvidia/nemotron-3.5-lightning-free")
IMAGE=os.environ.get("AUTOPILOT_IMAGE_MODEL","bfl/flux-3-image-klein")
VISION=os.environ.get("AUTOPILOT_VISION_MODEL","inclusionai/ling-3.0-flash-vl-free")

def ai(endpoint, body, key):
    r=urllib.request.Request(GATEWAY+endpoint, json.dumps(body).encode(),
        method="POST",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r,timeout=150) as f:
            return json.loads(f.read(18_000_000))
    except urllib.error.HTTPError as e:
        raise RuntimeError("AI_GATEWAY_HTTP_"+str(e.code)) from None

def chat(messages,key,model):
    r=ai("/chat/completions",{"model":model,"messages":messages,"temperature":0.7},key)
    value=(r.get("choices") or [{}])[0].get("message",{}).get("content")
    if not isinstance(value,str) or not value.strip():
        raise ValueError("No usable generated text")
    return value.strip()

def content(day,slot,key):
    language="en" if slot in ("09:30","19:30") else "zh-Hant"
    actor,appearance=(
        ("阿橘","orange tabby"),("小雪","white longhair"),
        ("小夜","black cat"),("阿斑","tuxedo cat"),("咪寶","playful tabby")
    )[(day.toordinal()+SLOTS.index(slot))%5]
    request=("Return JSON only with keys caption, scene, topic. Original funny or heartwarming "
        "fictional cat slice-of-life. No market/news claims, quotations, copyrighted characters, "
        "text in images, promotions or personal data. Caption at most 240 characters. "
        "Scene in English 30-70 words: one expressive cat, unique situation and pose, "
        "hand-painted book illustration, natural lighting, precise anatomy, no typography. "
        f"Taipei date {day} time {slot}. Caption language={language}. Character={actor}, {appearance}.")
    raw=chat([{"role":"system","content":"Produce one original family-friendly social post as JSON."},
              {"role":"user","content":request}],key,TEXT)
    item=json.loads(raw.strip().removeprefix("json").strip())
    if not 12<=len(item.get("caption",""))<=240 or not 30<=len(item.get("scene",""))<=700:
        raise ValueError("AI content failed length checks")
    if "http" in item["caption"].lower():
        raise ValueError("Unapproved link")
    return item,language

def make_image(scene,key):
    r=ai("/images/generations",{"model":IMAGE,"prompt":
        "Original wholesome painterly illustration, charming cat story, no lettering, no logos. "
        +scene,"n":1,"size":"1024x1024","response_format":"b64_json"},key)
    data=(r.get("data") or [{}])[0].get("b64_json")
    if not data: raise ValueError("Provider did not return supported base64 image")
    raw=base64.b64decode(data,validate=True)
    if len(raw)>16_000_000: raise ValueError("Image over size cap")
    with Image.open(io.BytesIO(raw)) as src:
        if min(src.size)<512: raise ValueError("Image too small")
        img=ImageOps.fit(ImageOps.exif_transpose(src).convert("RGB"),(1024,1024))
        output=io.BytesIO()
        img.save(output,format="JPEG",quality=82,optimize=True,progressive=True)
    jpg=output.getvalue()
    if not 25_000<len(jpg)<4_000_000: raise ValueError("Invalid JPEG")
    return jpg

def qa_image(jpg,scene,key):
    uri="data:image/jpeg;base64,"+base64.b64encode(jpg).decode()
    response=chat([{"role":"user","content":[
       {"type":"text","text":"Return ONLY PASS if the image clearly depicts a coherent cat illustration, with no inappropriate content, symbols, gibberish writing or watermark; else FAIL. "+scene},
       {"type":"image_url","image_url":{"url":uri}}]}],key,VISION)
    return response.strip()=="PASS"

def slots_to_fill(now):
    for days in range(3):
        day=now.date()+dt.timedelta(days=days)
        for slot in SLOTS:
            due=dt.datetime.fromisoformat(str(day)+"T"+slot).replace(tzinfo=TZ)
            lead=(due-now).total_seconds()
            record=ROOT/"state/meta_native"/(str(day)+"-"+slot.replace(":","")+".json")
            if 3600<lead<2.9*86400 and not record.exists():
                yield day,slot

def commit_queue(day,slot,item,language,jpg):
    digest=hashlib.sha256(jpg).hexdigest()
    image_file=ROOT/"assets"/(digest+".jpg")
    queue_file=ROOT/"queue/meta"/str(day)/(slot.replace(":","")+".json")
    if queue_file.exists(): raise ValueError("Never overwrite queued post")
    image_file.parent.mkdir(parents=True,exist_ok=True)
    queue_file.parent.mkdir(parents=True,exist_ok=True)
    image_file.write_bytes(jpg)
    record={"page_id":base.PAGE_ID,"slot":str(day)+"T"+slot,
        "caption":item["caption"],"language":language,"image_sha256":digest,
        "image_url":base.ASSET_BASE+digest+".jpg",
        "image_qa":True,"image_qa_method":"vision model PASS + JPEG integrity",
        "source_record":"AI Gateway original from prompt","image_model":IMAGE,
        "text_model":TEXT,"vision_model":VISION,"topic":str(item.get("topic",""))[:80]}
    base.write(queue_file,record)
    for args in (["add",str(image_file.relative_to(ROOT)),str(queue_file.relative_to(ROOT))],
        ["-c","user.name=cat-autopilot[bot]","-c","user.email=cat-autopilot@users.noreply.github.com",
          "commit","-m","Prepare original cat post "+record["slot"]],
        ["push","origin","HEAD:main"]):
        cmd=subprocess.run(["git",*args],cwd=ROOT,capture_output=True)
        if cmd.returncode: raise RuntimeError("Git commit/push conflict; Meta untouched")
    return record

def run(dry=False):
    now=dt.datetime.now(TZ)
    targets=list(slots_to_fill(now))
    print("FUTURE_SLOTS_TO_FILL="+str(len(targets)),flush=True)
    if dry: return
    if os.environ.get("CAT_AUTOPILOT_ENABLED")!="true":
        raise ValueError("Autopilot explicitly disabled")
    meta=os.environ.get("META_PAGE_ACCESS_TOKEN")
    key=os.environ.get("AI_GATEWAY_API_KEY")
    if not meta or not key:
        raise ValueError("Credentials missing; no Facebook or AI write attempted")
    # Check Meta authorization before AI usage to avoid spending on unusable posts.
    native.remote(meta)
    for day,slot in targets:
        qpath=ROOT/"queue/meta"/str(day)/(slot.replace(":","")+".json")
        if qpath.exists():
            q=base.read(qpath)
        else:
            item,language=content(day,slot,key)
            existing=[base.norm(base.read(p).get("caption",""))
                      for p in (ROOT/"queue/meta").glob("*/*.json")]
            if base.norm(item["caption"]) in existing:
                raise ValueError("AI generated duplicate caption")
            image=make_image(item["scene"],key)
            if not qa_image(image,item["scene"],key):
                print("VISUAL_QA_REJECTED "+str(day)+" "+slot,flush=True)
                continue
            q=commit_queue(day,slot,item,language,image)
        try:
            base.verify_image(q)
        except Exception:
            print("PUBLIC_IMAGE_NOT_READY: retry same queue on next replenishment",flush=True)
            continue
        native.schedule(q,meta,dt.datetime.now(TZ))
        print("META_NATIVE_SCHEDULED "+q["slot"],flush=True)

if __name__=="__main__":
    try: run("--dry-run" in sys.argv)
    except Exception as e:
        print("AUTOPILOT_STOP "+type(e).__name__+": "+str(e)[:180],file=sys.stderr)
        sys.exit(1)
