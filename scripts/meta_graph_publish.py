#!/usr/bin/env python3
"""Official Meta Graph photo publisher. Fail closed; never retry an unknown write."""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

PAGE_ID = "1346385028565797"
GRAPH_VERSION = "v26.0"  # Reconfirm version and permissions before enabling
TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
SLOTS = {"09:30", "12:30", "16:30", "19:30"}
ASSET_BASE = "https://gxaawill2-ui.github.io/cat-page-autopilot/assets/"
WINDOW_MIN = 45

def sha(b):
    return hashlib.sha256(b).hexdigest()

def norm(t):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip()

def read(p):
    return json.loads(p.read_text(encoding="utf-8"))

def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError("Git CAS commit/push rejected; STOP, never send Facebook write")
    return p.stdout.strip()

def persist(p, message):
    git("add", str(p.relative_to(ROOT)))
    git("-c", "user.name=cat-page-publisher[bot]",
        "-c", "user.email=cat-page-publisher@users.noreply.github.com",
        "commit", "-m", message)
    git("push", "origin", "HEAD:main")

def graph(path, token, params=None, method="GET"):
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path.lstrip('/')}"
    if method == "GET" and params:
        url += "?" + urllib.parse.urlencode(params)
    data = urllib.parse.urlencode(params).encode() if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "cat-page-official-meta/1"
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read(200_000))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Meta HTTP {e.code}; never retry this write without reconciliation") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Meta transport result uncertain; never automatically retry") from None

def queue_path(day, slot):
    return ROOT / "queue/meta" / day / (slot.replace(":", "") + ".json")

def result_path(day, slot):
    return ROOT / "state/meta_dispatch" / (day + "-" + slot.replace(":", "") + ".json")

def validate(q, day, slot):
    if q.get("page_id") != PAGE_ID or q.get("slot") != f"{day}T{slot}":
        raise ValueError("Wrong Page or slot; no backfill")
    caption, image_sha = q.get("caption"), q.get("image_sha256")
    if not isinstance(caption, str) or not caption.strip() or len(caption) > 10000:
        raise ValueError("Invalid caption")
    if not isinstance(image_sha, str) or not re.fullmatch("[0-9a-f]{64}", image_sha):
        raise ValueError("Invalid image SHA")
    if q.get("image_url") != ASSET_BASE + image_sha + ".jpg":
        raise ValueError("Untrusted image URL")
    if q.get("language") not in ("en", "zh-Hant", "ja"):
        raise ValueError("Unsupported language")
    expected = "en" if slot in ("09:30", "19:30") else "zh-Hant"
    if slot == "19:30" and day in ("2026-11-03", "2026-11-06"):
        expected = "ja"
    if q["language"] != expected:
        raise ValueError("Language does not match authorized slot")

def policy_gate(day, slot):
    policy = read(ROOT / "state/policy.json")
    if (policy.get("mode") != "live" or policy.get("page_id") != PAGE_ID
            or policy.get("timezone") != "Asia/Taipei"):
        raise ValueError("POLICY_GATE: live Page and timezone required")
    limit = policy.get("daily_limit")
    if type(limit) is not int or not 1 <= limit <= 4:
        raise ValueError("Invalid daily limit")
    # Count even unknown attempts; an absent receipt is not an unused slot.
    occupied = set()
    for folder in ("state/posts", "state/meta_dispatch"):
        for path in (ROOT / folder).glob("*.json"):
            old = read(path)
            if old.get("slot"):
                stamp = dt.datetime.fromisoformat(old["slot"])
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=TZ)
                stamp = stamp.astimezone(TZ)
                if stamp.date().isoformat() == day:
                    occupied.add(stamp.strftime("%H:%M"))
    if slot in occupied:
        raise ValueError("SLOT_RESERVED by existing pipeline")
    if len(occupied) >= limit:
        raise ValueError("DAILY_LIMIT includes unknown attempts")

def local_dedup(q):
    for path in (ROOT / "state/posts").glob("*.json"):
        old = read(path)
        if norm(old.get("caption", "")) == norm(q["caption"]) or old.get("image_sha256") == q["image_sha256"]:
            raise ValueError("Same old or unknown image/caption; publishing prohibited")
    for path in (ROOT / "state/meta_dispatch").glob("*.json"):
        old = read(path)
        if old.get("caption_sha256") == sha(norm(q["caption"]).encode()) or old.get("image_sha256") == q["image_sha256"]:
            raise ValueError("Meta publisher already attempted this content")

def remote_dedup(q, token):
    identity = graph("me", token, {"fields": "id,name"})
    if identity.get("id") != PAGE_ID:
        raise ValueError("Token does not represent the authorized Page")
    posts = graph(f"{PAGE_ID}/posts", token, {"fields": "id,message,created_time", "limit": 40})
    if not isinstance(posts.get("data"), list):
        raise ValueError("Cannot verify Meta recent posts")
    if any(norm(p.get("message") or "") == norm(q["caption"]) for p in posts["data"]):
        raise ValueError("Meta already contains same caption")
    day = q["slot"].split("T")[0]
    today = [p for p in posts["data"] if dt.datetime.fromisoformat(
        p["created_time"].replace("Z", "+00:00")).astimezone(TZ).date().isoformat() == day]
    observed_ids = {p["id"] for p in today}
    potential = set()
    for folder in ("state/posts", "state/meta_dispatch"):
        for path in (ROOT / folder).glob("*.json"):
            old = read(path)
            if not old.get("slot"):
                continue
            stamp = dt.datetime.fromisoformat(old["slot"])
            stamp = (stamp.replace(tzinfo=TZ) if stamp.tzinfo is None else stamp.astimezone(TZ))
            post_id = old.get("meta_post_id") or old.get("post_id")
            if stamp.date().isoformat() == day and post_id not in observed_ids:
                potential.add(old["slot"])
    if len(observed_ids) + len(potential) >= min(4, read(ROOT / "state/policy.json")["daily_limit"]):
        raise ValueError("REMOTE_DAILY_LIMIT reached")

def readback_matches(p, post_id, photo_id, caption):
    if p.get("id") != post_id or norm(p.get("message") or "") != norm(caption):
        return False
    attachments = p.get("attachments", {}).get("data", [])
    return bool(p.get("full_picture") and p.get("permalink_url") and any(
        a.get("target", {}).get("id") == photo_id and a.get("media", {}).get("image", {}).get("src")
        for a in attachments))

def verify_image(q):
    req = urllib.request.Request(q["image_url"], headers={"User-Agent": "cat-page-image/1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        status = r.status
        mime = (r.headers.get("Content-Type") or "").lower().split(";")[0]
        image = r.read(4_000_001)
    if status != 200 or mime != "image/jpeg" or len(image) > 4_000_000 or sha(image) != q["image_sha256"]:
        raise ValueError("Public JPEG status, MIME or SHA failed")

def preflight():
    """Read-only Meta connectivity check; independent of queue, slot and live switch."""
    token = os.environ.get("META_PAGE_ACCESS_TOKEN")
    if not token:
        raise ValueError("PREFLIGHT_TOKEN_MISSING")
    identity = graph("me", token, {"fields": "id,name"})
    if identity.get("id") != PAGE_ID:
        raise ValueError("PREFLIGHT_WRONG_PAGE")
    posts = graph(f"{PAGE_ID}/posts", token, {"fields":"id,message,created_time", "limit":40})
    if not isinstance(posts.get("data"), list):
        raise ValueError("PREFLIGHT_POST_LIST_UNAVAILABLE")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    proof = {"validator":"github-actions-meta-get-preflight", "page_id":PAGE_ID,
             "page_name":identity.get("name"), "graph_version":GRAPH_VERSION,
             "checked_at":dt.datetime.now(TZ).isoformat(), "run_id":run_id,
             "source_commit":os.environ.get("GITHUB_SHA"),
             "recent_posts":[{"id":p.get("id"),"created_time":p.get("created_time")} for p in posts["data"]],
             "facebook_post_calls":0, "write_permission_tested":False,
             "note":"GET success is not Facebook publishing acceptance; no Token stored in this proof."}
    out = ROOT / "records/meta-preflight" / (run_id + ".json")
    write(out, proof)
    if run_id != "local":
        persist(out, "Record read-only Meta official preflight " + run_id)
    print("META_PREFLIGHT_OK_PAGE=" + PAGE_ID + "; FACEBOOK_POST_CALLS=0")
    return proof

def run(slot, dry_run=False, now=None):
    if slot not in SLOTS:
        raise ValueError("Invalid slot")
    now = now or dt.datetime.now(TZ)
    day = now.date().isoformat()
    planned = dt.datetime.fromisoformat(f"{day}T{slot}").replace(tzinfo=TZ)
    mins = (now - planned).total_seconds()/60
    # Safe, non-sensitive schedule diagnostics. GitHub cron is best effort.
    print(f"DISPATCH_DIAG slot={day}T{slot} now_taipei={now.isoformat()} "
          f"delay_min={mins:.2f} allowed_window_min={WINDOW_MIN} "
          f"run_id={os.environ.get('GITHUB_RUN_ID', 'local')} "
          f"event={os.environ.get('GITHUB_EVENT_NAME', 'local')}", flush=True)
    if not 0 <= mins <= WINDOW_MIN:
        reason = "EARLY" if mins < 0 else "STALE"
        print(f"SKIPPED_STALE_OR_EARLY reason={reason} delay_min={mins:.2f}; NEVER_BACKFILL")
        return "skipped"
    queue = queue_path(day, slot)
    if not queue.exists():
        print("NO_QUEUED_CONTENT")
        return "skipped"
    q = read(queue)
    validate(q, day, slot)
    out = result_path(day, slot)
    if out.exists():
        print("SLOT_ALREADY_ATTEMPTED_NEVER_RETRY")
        return "skipped"
    policy_gate(day, slot)
    local_dedup(q)
    if dry_run:
        print("DRY_RUN_OK_NO_FACEBOOK_WRITES")
        return "dry-run"
    if os.environ.get("META_PUBLISH_ENABLED") != "true":
        print("META_PUBLISH_DISABLED")
        return "skipped"
    token = os.environ.get("META_PAGE_ACCESS_TOKEN")
    if not token:
        print("META_PAGE_ACCESS_TOKEN_SECRET_MISSING")
        return "skipped"
    remote_dedup(q, token)
    verify_image(q)
    record = {"page_id": PAGE_ID, "slot": q["slot"],
              "status": "armed_unknown_until_reconciled",
              "caption_sha256": sha(norm(q["caption"]).encode()),
              "image_sha256": q["image_sha256"],
              "armed_at": now.isoformat(),
              "meta_post_id": None, "photo_id": None,
              "note": "A committed arm is never replayed, even after tool timeout."}
    write(out, record)
    persist(out, f"Arm Meta official slot {day} {slot}")
    # EXACTLY one POST, with no retry. A Git push failure above prevents all writes.
    try:
        response = graph(f"{PAGE_ID}/photos", token, {
            "url": q["image_url"], "caption": q["caption"], "published": "true"
        }, method="POST")
    except Exception:
        print("META_WRITE_UNKNOWN_KEEP_ARMED_NEVER_RETRY")
        return "unknown"
    post_id, photo_id = response.get("post_id"), response.get("id")
    record.update(status="published_unverified" if post_id else "unknown_photo_id_only",
                  meta_post_id=post_id, photo_id=photo_id,
                  response_at=dt.datetime.now(TZ).isoformat())
    write(out, record)
    try:
        persist(out, f"Record Meta response for {day} {slot}")
    except Exception:
        if post_id:
            print("META_POST_ID_FOR_RECONCILIATION=" + str(post_id))
        print("RESPONSE_NOT_DURABLE_NEVER_RETRY")
        return "unknown"
    if not post_id:
        print("ONLY_PHOTO_ID_NO_POST_ID; NEED_MANUAL_VERIFICATION")
        return "unknown"
    try:
        p = graph(post_id, token, {"fields": "id,message,permalink_url,created_time,full_picture,attachments{target,media}"})
        if readback_matches(p, post_id, photo_id, q["caption"]):
            record.update(status="verified_api", permalink_url=p.get("permalink_url"),
                          full_picture=p["full_picture"], attachment_photo_id=photo_id,
                          visual_review="pending; API identity check is not visual QA",
                          verified_at=dt.datetime.now(TZ).isoformat())
            write(out, record)
            persist(out, f"Verify Meta official post {day} {slot}")
            print("META_VERIFIED_POST_ID=" + post_id)
            return "verified"
    except Exception:
        pass
    print("PUBLISHED_BUT_READBACK_INCOMPLETE_POST_ID=" + str(post_id))
    return "published_unverified"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", choices=sorted(SLOTS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    try:
        if args.preflight:
            preflight()
        elif args.slot:
            run(args.slot, dry_run=args.dry_run)
        else:
            parser.error("--slot or --preflight required")
    except Exception as exc:
        print("SAFETY_STOP:", str(exc), file=sys.stderr)
        raise SystemExit(1)
