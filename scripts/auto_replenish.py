#!/usr/bin/env python3
"""Prepare AI-original future cat posts and submit them once to Meta native scheduler.
Fail closed; never post immediately and never replay uncertain writes.
"""
import base64, datetime as dt, hashlib, io, json, os, re, subprocess, sys
import urllib.request, urllib.error
from decimal import Decimal
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
VISION=os.environ.get("AUTOPILOT_VISION_MODEL","openai/gpt-5-nano")

def budget_gate(now):
    """Dashboard budgets are soft caps, not proof of zero paid spend."""
    p=ROOT/"state/autopilot_budget.json"
    if not p.exists(): raise ValueError("ZERO_PAID_SPEND_NOT_VERIFIED")
    b=base.read(p)
    required=("verified", "free_credits_only", "auto_topup_disabled",
              "no_paid_balance", "no_invoice_billing", "no_byok", "provider_hard_stop")
    if any(b.get(k) is not True for k in required) or not b.get("evidence_record"):
        raise ValueError("ZERO_PAID_SPEND_NOT_VERIFIED")
    if native.stamp(b["valid_until"]) <= now:
        raise ValueError("ZERO_PAID_SPEND_EVIDENCE_EXPIRED")

def model_gate():
    """Inspect the live catalog before spending; never silently replace a model."""
    with urllib.request.urlopen(GATEWAY+"/models",timeout=30) as response:
        models={m["id"]:m for m in json.loads(response.read(4_000_000))["data"]}
    for mid,inputs,output in ((TEXT,("text",),"text"),(IMAGE,("text",),"image"),
                              (VISION,("text","image"),"text")):
        modes=models.get(mid,{}).get("modalities",{})
        if not set(inputs).issubset(modes.get("input",[])) or output not in modes.get("output",[]):
            raise ValueError("MODEL_UNAVAILABLE_OR_WRONG_MODALITY: "+mid)
    if Decimal(models[TEXT]["pricing"]["input"])!=0 or Decimal(models[TEXT]["pricing"]["output"])!=0:
        raise ValueError("Text model no longer free")
    if Decimal(models[IMAGE]["pricing"]["image"])>Decimal("0.009"):
        raise ValueError("Image price exceeds reviewed ceiling")
    if (Decimal(models[VISION]["pricing"]["input"])>Decimal("0.00000005") or
            Decimal(models[VISION]["pricing"]["output"])>Decimal("0.0000004")):
        raise ValueError("Vision price exceeds reviewed ceiling")

def slot_language(day,slot):
    if slot=="19:30" and str(day) in ("2026-11-03","2026-11-06"):
        return "ja"
    return "en" if slot in ("09:30","19:30") else "zh-Hant"

def ai(endpoint, body, key):
    r=urllib.request.Request(GATEWAY+endpoint, json.dumps(body).encode(),
        method="POST",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(r,timeout=150) as f:
            return json.loads(f.read(18_000_000))
    except urllib.error.HTTPError as e:
        raise RuntimeError("AI_GATEWAY_HTTP_"+str(e.code)) from None

def chat(messages,key,model):
    r=ai("/chat/completions",{"model":model,"messages":messages,"max_tokens":1000},key)
    value=(r.get("choices") or [{}])[0].get("message",{}).get("content")
    if not isinstance(value,str) or not value.strip():
        raise ValueError("No usable generated text")
    return value.strip()

def content(day,slot,key):
    language=slot_language(day,slot)
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
    if raw.startswith("```json\n") and raw.endswith("```"):
        raw=raw[8:-3].strip()
    item=json.loads(raw)
    if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ("caption","scene","topic")):
        raise ValueError("AI content is not the required JSON object")
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

def generation_file(day,slot):
    return ROOT/"records/generation"/str(day)/(slot.replace(":","")+".json")

def checkpoint(path,value,message):
    base.write(path,value)
    base.persist(path,message)

def commit_queue(day,slot,item,language,jpg):
    digest=hashlib.sha256(jpg).hexdigest()
    image_file=ROOT/"docs/assets"/(digest+".jpg")
    queue_file=ROOT/"queue/meta"/str(day)/(slot.replace(":","")+".json")
    if queue_file.exists(): raise ValueError("Never overwrite queued post")
    image_file.parent.mkdir(parents=True,exist_ok=True)
    queue_file.parent.mkdir(parents=True,exist_ok=True)
    image_file.write_bytes(jpg)
    record={"page_id":base.PAGE_ID,"slot":str(day)+"T"+slot,
        "caption":item["caption"],"language":language,"image_sha256":digest,
        "image_url":base.ASSET_BASE+digest+".jpg",
        "image_qa":False,"image_qa_method":"pending; never schedule before vision PASS",
        "scene":item["scene"],"prepared_at":dt.datetime.now(TZ).isoformat(),
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
    budget_gate(now)
    model_gate()
    for day,slot in targets:
        qpath=ROOT/"queue/meta"/str(day)/(slot.replace(":","")+".json")
        if qpath.exists():
            q=base.read(qpath)
        else:
            gp=generation_file(day,slot)
            if gp.exists():
                print("GENERATION_NEEDS_RECONCILIATION "+str(day)+" "+slot,flush=True)
                continue
            stage={"slot":str(day)+"T"+slot,"status":"content_armed_unknown",
                   "attempts":1,"retry_allowed":False,"started_at":dt.datetime.now(TZ).isoformat()}
            checkpoint(gp,stage,"Save AI generation intent "+stage["slot"])
            item,language=content(day,slot,key)
            stage.update(status="image_armed_unknown",content=item,language=language)
            checkpoint(gp,stage,"Save caption and original scene before image request")
            existing=[base.norm(base.read(p).get("caption",""))
                      for p in (ROOT/"queue/meta").glob("*/*.json")]
            if base.norm(item["caption"]) in existing:
                raise ValueError("AI generated duplicate caption")
            image=make_image(item["scene"],key)
            q=commit_queue(day,slot,item,language,image)
            # Persist the actual JPEG before another external request can interrupt Work.
            stage.update(status="jpeg_durable_qa_pending",image_sha256=q["image_sha256"])
            checkpoint(gp,stage,"Record durable original image before visual QA")
        if q.get("image_qa") is not True:
            if q.get("image_qa_method")=="vision FAIL; held":
                continue
            image_path=ROOT/"docs/assets"/(q["image_sha256"]+".jpg")
            image=image_path.read_bytes()
            if base.sha(image)!=q["image_sha256"]: raise ValueError("Persisted image SHA mismatch")
            passed=qa_image(image,q["scene"],key)
            q.update(image_qa=passed,image_qa_method="vision PASS + JPEG integrity" if passed else "vision FAIL; held")
            checkpoint(qpath,q,"Save actual visual QA decision "+q["slot"])
            if not passed:
                print("VISUAL_QA_REJECTED "+str(day)+" "+slot,flush=True)
                continue
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
