#!/usr/bin/env python3
"""Prepare Meta-native scheduled posts. Never publishes immediately, never retries a write."""
import argparse
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import meta_graph_publish as base

ROOT = base.ROOT
PAGE = base.PAGE_ID
TZ = base.TZ

class Rejected(RuntimeError):
    pass

def api(path, token, params=None, method="GET"):
    url = f"https://graph.facebook.com/{base.GRAPH_VERSION}/{path}"
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    data = urllib.parse.urlencode(params).encode() if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.loads(response.read(400000))
    except urllib.error.HTTPError as exc:
        try:
            e = json.loads(exc.read(20000)).get("error", {})
        except Exception:
            e = {}
        safe = {k:e.get(k) for k in ("code", "error_subcode", "type", "message", "fbtrace_id")}
        text = re.sub(r"\bEAA[A-Za-z0-9_-]+\b", "[REDACTED]", json.dumps(safe, ensure_ascii=False))
        raise Rejected(f"Meta HTTP {exc.code}: {text}") from None

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, value, message):
    base.write(path, value)
    base.persist(path, message)

def entries():
    for folder in ("state/posts", "state/meta_dispatch", "state/meta_native"):
        for p in (ROOT / folder).glob("*.json"):
            yield load(p)
    # A durable curated reservation consumes capacity before any external write.
    # Once its native attempt exists, that exact attempt owns the slot instead.
    for p in (ROOT / "state/curated_reservations").glob("*.json"):
        reservation = load(p)
        if not record_file(reservation).exists():
            yield reservation

def curated_reservation(q):
    identity = q.get("curated_id")
    if not isinstance(identity, str) or not re.fullmatch(r"[a-z0-9-]{1,80}", identity):
        return None
    path = ROOT / "state/curated_reservations" / (identity + ".json")
    if not path.exists():
        return None
    r = load(path)
    keys = ("page_id", "slot", "caption", "language", "image_sha256", "image_url", "curated_id", "source_png_sha256")
    if (r.get("status") != "reserved" or r.get("source") != "ChatGPT original; user-selected"
            or not re.fullmatch(r"[0-9a-f]{64}", str(r.get("source_png_sha256", "")))
            or any(r.get(k) != q.get(k) for k in keys)):
        return None
    return r

def owns_reservation(q, old):
    return curated_reservation(q) is not None and old.get("curated_id") == q.get("curated_id") and old.get("status") == "reserved"

def stamp(value):
    if isinstance(value, (int, float)) or (isinstance(value,str) and value.isdigit()):
        return dt.datetime.fromtimestamp(int(value), TZ)
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=TZ) if parsed.tzinfo is None else parsed.astimezone(TZ)

def queue_file(value):
    if not re.fullmatch(r"queue/meta/\d{4}-\d{2}-\d{2}/(?:0930|1230|1630|1930)\.json", value):
        raise ValueError("Only a canonical future queue path is permitted")
    return ROOT / value

def record_file(q):
    return ROOT / "state/meta_native" / (q["slot"].replace(":", "").replace("T", "-") + ".json")

def validate(q, now):
    planned = stamp(q["slot"])
    reserved = curated_reservation(q)
    if q.get("curated_id") and reserved is None:
        raise ValueError("Curated content must match its immutable authorized reservation")
    if reserved:
        # Reuse ordinary payload validation without changing the standard language slots.
        # Only the exact durable curated reservation authorizes a different future time.
        validation_slot = "09:30" if q["language"] == "en" else "12:30"
        if q["language"] not in ("en", "zh-Hant"):
            raise ValueError("Curated language not authorized")
        copy = dict(q, slot=planned.date().isoformat()+"T"+validation_slot)
        base.validate(copy, planned.date().isoformat(), validation_slot)
    else:
        if planned.strftime("%H:%M") not in base.SLOTS:
            raise ValueError("Nonstandard slot requires curated reservation")
        base.validate(q, planned.date().isoformat(), planned.strftime("%H:%M"))
    if q.get("image_qa") is not True:
        raise ValueError("Original image visual QA required")
    if not 15*60 <= (planned-now).total_seconds() <= 3*86400:
        raise ValueError("Native schedule must be 15 minutes to 3 days ahead; no backfill")
    policy = load(ROOT / "state/policy.json")
    if (policy.get("mode") != "live" or policy.get("page_id") != PAGE or
            policy.get("timezone") != "Asia/Taipei" or type(policy.get("daily_limit")) is not int
            or not 1 <= policy["daily_limit"] <= 4):
        raise ValueError("Live policy, Page, Taipei and max-four cap required")
    if record_file(q).exists():
        raise ValueError("Native slot already attempted; never replay unknown or completed")
    for old in entries():
        if owns_reservation(q, old):
            continue
        if old.get("slot") == q["slot"]:
            raise ValueError("Slot already occupied")
        if (old.get("caption_sha256") == base.sha(base.norm(q["caption"]).encode())
                or old.get("image_sha256") == q["image_sha256"]):
            raise ValueError("Historical caption/image is blocked, including unknown attempts")
    for path in (ROOT / "queue/meta").glob("*/*.json"):
        old = load(path)
        if old.get("slot") == q["slot"]:
            continue
        if old.get("image_sha256") == q["image_sha256"] or base.norm(old.get("caption", "")) == base.norm(q["caption"]):
            raise ValueError("Another past/future queue already uses this content")
    return planned, policy["daily_limit"]

def remote(token):
    identity = api("me", token, {"fields":"id,name"})
    if identity.get("id") != PAGE:
        raise ValueError("Token is not the exact authorized Page")
    result = {}
    for edge in ("posts", "scheduled_posts"):
        data = api(PAGE+"/"+edge, token, {
            "fields":"id,message,created_time,is_published,scheduled_publish_time,permalink_url", "limit":100})
        if not isinstance(data.get("data"), list) or data.get("paging", {}).get("next"):
            raise ValueError("Cannot establish complete bounded Page list")
        result[edge] = data["data"]
    return identity, result

def remote_guard(q, planned, cap, lists):
    all_remote = lists["posts"] + lists["scheduled_posts"]
    if any(base.norm(x.get("message", "")) == base.norm(q["caption"]) for x in all_remote):
        raise ValueError("Meta already has this caption")
    day = planned.date()
    actual = set()
    for x in all_remote:
        when = x.get("scheduled_publish_time") or x.get("created_time")
        if when and abs((stamp(when)-planned).total_seconds()) < 90*60:
            raise ValueError("Minimum 90-minute separation from a real Meta post")
        if when and stamp(when).date() == day:
            actual.add(x["id"])
        if x.get("scheduled_publish_time") and stamp(x["scheduled_publish_time"]) == planned:
            raise ValueError("Meta native slot already occupied")
    potential = set()
    for old in entries():
        if owns_reservation(q, old):
            continue
        if old.get("slot") and old.get("status") not in ("upload_rejected", "schedule_rejected"):
            if abs((stamp(old["slot"])-planned).total_seconds()) < 90*60:
                raise ValueError("Minimum 90-minute separation from a reserved or uncertain slot")
        if old.get("slot") and stamp(old["slot"]).date() == day:
            oid = old.get("meta_post_id") or old.get("post_id")
            if oid not in actual and old.get("status") not in ("upload_rejected", "schedule_rejected"):
                potential.add(old["slot"])
    if len(actual) + len(potential) >= cap:
        raise ValueError("Daily cap reached including scheduled, published and uncertain attempts")

def safe_post(p):
    return {k:p.get(k) for k in ("id", "message", "created_time", "is_published", "scheduled_publish_time", "permalink_url")}

def audit(token):
    identity, lists = remote(token)
    proof = {"page_id":identity["id"], "page_name":identity.get("name"),
             "checked_at":dt.datetime.now(TZ).isoformat(), "facebook_write_calls":0,
             **{k:[safe_post(p) for p in v] for k,v in lists.items()}}
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    save(ROOT / "records/meta-native" / ("audit-"+run_id+".json"), proof, "Read Meta published and scheduled posts "+run_id)
    print("META_NATIVE_AUDIT_OK_PAGE="+PAGE+"; FACEBOOK_WRITE_CALLS=0")

def reconcile(q, record, token):
    post_id = record.get("meta_post_id")
    if not post_id:
        raise ValueError("No real post ID; keep unresolved, never recreate")
    p = api(post_id, token, {"fields":"id,message,is_published,scheduled_publish_time,created_time,permalink_url,full_picture,attachments{target,media}"})
    attachments = p.get("attachments", {}).get("data", [])
    picture = bool(p.get("full_picture") and any(a.get("target", {}).get("id") == record["photo_id"] for a in attachments))
    text_ok = p.get("id") == post_id and base.norm(p.get("message", "")) == base.norm(q["caption"])
    schedule_ok = p.get("is_published") is False and int(p.get("scheduled_publish_time") or 0) == record["scheduled_publish_time"]
    published_ok = p.get("is_published") is True
    record.update(readback=safe_post(p), full_picture_present=bool(p.get("full_picture")),
                  attachment_photo_id_matches=picture, caption_matches=text_ok,
                  checked_at=dt.datetime.now(TZ).isoformat(), planner_verified=record.get("planner_verified", False),
                  visual_review=record.get("visual_review", "pending"))
    if text_ok and picture and published_ok:
        record.update(status="published_api_verified", permalink_url=p.get("permalink_url"),
                      actual_created_time=p.get("created_time"))
    elif text_ok and picture and schedule_ok:
        record["status"] = "scheduled_api_verified"
    else:
        record["status"] = "post_readback_unverified"
    save(record_file(q), record, "Read back Meta native post "+post_id)
    print(json.dumps({"status":record["status"], "post_id":post_id,
                      "is_published":p.get("is_published"), "scheduled_publish_time":p.get("scheduled_publish_time")},ensure_ascii=False))
    return record

def schedule(q, token, now):
    planned, cap = validate(q, now)
    _, lists = remote(token)
    remote_guard(q, planned, cap, lists)
    base.verify_image(q)
    record = {"page_id":PAGE, "slot":q["slot"], "status":"upload_armed_unknown",
              "caption_sha256":base.sha(base.norm(q["caption"]).encode()), "image_sha256":q["image_sha256"],
              "scheduled_publish_time":int(planned.timestamp()), "armed_at":now.isoformat(),
              "photo_id":None, "meta_post_id":None, "retry_allowed":False,
              "method":"Meta unpublished photo -> scheduled Page feed", "run_id":os.environ.get("GITHUB_RUN_ID")}
    if q.get("curated_id"):
        record.update(curated_id=q["curated_id"], source_png_sha256=q["source_png_sha256"])
    save(record_file(q), record, "Arm unpublished photo for future Meta slot "+q["slot"])
    try:
        photo = api(PAGE+"/photos", token, {"url":q["image_url"], "published":"false"}, method="POST")
    except Rejected as exc:
        record.update(status="upload_rejected", error=str(exc));save(record_file(q), record, "Record native photo rejection")
        raise
    if not re.fullmatch(r"\d+", str(photo.get("id", ""))):
        raise ValueError("No photo ID; upload outcome uncertain, never retry")
    record.update(photo_id=photo["id"], status="photo_uploaded_not_scheduled")
    save(record_file(q), record, "Save unpublished photo ID "+photo["id"])
    if (planned-dt.datetime.now(TZ)).total_seconds() < 10*60:
        raise ValueError("Preparation consumed lead time; photo remains unpublished, do not reschedule automatically")
    record["status"] = "schedule_armed_unknown"
    save(record_file(q), record, "Arm native feed schedule "+q["slot"])
    try:
        post = api(PAGE+"/feed", token, {"message":q["caption"], "published":"false",
                   "scheduled_publish_time":str(record["scheduled_publish_time"]),
                   "unpublished_content_type":"SCHEDULED",
                   "attached_media[0]":json.dumps({"media_fbid":record["photo_id"]})}, method="POST")
    except Rejected as exc:
        record.update(status="schedule_rejected", error=str(exc));save(record_file(q),record,"Record native feed rejection")
        raise
    post_id = str(post.get("id", ""))
    if not re.fullmatch(PAGE+r"_\d+", post_id):
        raise ValueError("Only photo/unknown ID returned; not a scheduled post, never retry")
    record.update(meta_post_id=post_id, status="scheduled_unverified", response_at=dt.datetime.now(TZ).isoformat())
    save(record_file(q), record, "Save genuine Meta scheduled post ID "+post_id)
    return reconcile(q, record, token)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["audit","dry-run","schedule","verify","curated"], default="dry-run")
    parser.add_argument("--queue", default="")
    args=parser.parse_args()
    token=os.environ.get("META_PAGE_ACCESS_TOKEN")
    if args.mode == "dry-run":
        q=load(queue_file(args.queue));validate(q,dt.datetime.now(TZ));print("NATIVE_DRY_RUN_OK_NO_META_WRITES");return
    if not token:
        raise ValueError("META_PAGE_ACCESS_TOKEN missing; no write possible")
    if args.mode == "audit":
        audit(token);return
    if args.mode == "curated":
        from curated_schedule import run
        run(token);return
    q=load(queue_file(args.queue))
    if args.mode == "verify":
        reconcile(q, load(record_file(q)), token)
    else:
        schedule(q, token, dt.datetime.now(TZ))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        message=re.sub(r"\bEAA[A-Za-z0-9_-]+\b", "[REDACTED]", str(exc))
        print("NATIVE_SAFETY_STOP: "+message)
        raise SystemExit(1)
