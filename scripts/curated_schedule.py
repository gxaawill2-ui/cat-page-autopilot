"""Schedule the exact user-selected originals, sharing the native CAS/unknown guards.
No AI, no immediate publishing, no overwrite or automatic retry of an existing attempt.
Run only inside the existing cat-page-meta-official-publisher concurrency group.
"""
import datetime as dt
import os
import time
import meta_native_schedule as native
import meta_graph_publish as base
import auto_replenish

def run(token):
    if os.environ.get("CAT_AUTOPILOT_ENABLED") != "true":
        raise ValueError("Live existing system switch required")
    native.audit(token)
    reservations = [native.load(p) for p in sorted((native.ROOT/"state/curated_reservations").glob("*.json"))]
    reservations.sort(key=lambda x:x["slot"])
    report = {"run_id":os.environ.get("GITHUB_RUN_ID"),"ai_calls":0,"immediate_publish_calls":0,
              "scheduled":[],"held":[],"started_at":dt.datetime.now(native.TZ).isoformat()}
    auto_replenish.request_pages_build()
    for r in reservations:
        qpath=native.ROOT/"queue/meta"/r["slot"][:10]/(r["slot"][11:].replace(":","")+".json")
        q=native.load(qpath)
        record=native.record_file(q)
        if record.exists():
            old=native.load(record)
            if old.get("meta_post_id"):
                native.reconcile(q,old,token)
            report["held"].append({"slot":q["slot"],"reason":"Existing attempt; never schedule again"})
            continue
        try:
            native.validate(q,dt.datetime.now(native.TZ))
            proof={"slot":q["slot"],"image_sha256":q["image_sha256"],"verified":False}
            for attempt in range(3):
                try:
                    base.verify_image(q)
                    proof.update(verified=True,http_status=200,mime="image/jpeg",sha_matches=True,
                                 checked_at=dt.datetime.now(native.TZ).isoformat())
                    break
                except Exception as exc:
                    proof["last_error"]=type(exc).__name__
                    if attempt<2:time.sleep(40)
            native.save(native.ROOT/"records/pages-proofs"/(q["image_sha256"]+".json"),proof,"Validate curated original public JPEG")
            if not proof["verified"]:raise ValueError("Public JPEG HTTP/MIME/SHA validation failed")
            result=native.schedule(q,token,dt.datetime.now(native.TZ))
            report["scheduled"].append({"slot":q["slot"],"post_id":result["meta_post_id"],"status":result["status"]})
        except Exception as exc:
            report["held"].append({"slot":q["slot"],"reason":str(exc)[:300]})
            # Unknown writes or CAS failures stop the batch, never re-send.
            if not isinstance(exc,(ValueError,native.Rejected)):break
    report["completed_at"]=dt.datetime.now(native.TZ).isoformat()
    native.save(native.ROOT/"records/curated-runs"/(str(os.environ.get("GITHUB_RUN_ID","local"))+".json"),report,"Save actual curated schedule results")
    print(__import__('json').dumps(report,ensure_ascii=False))
    if any(x.get("reason")!="Existing attempt; never schedule again" for x in report["held"]):
        raise ValueError("Curated batch has held content; review actual evidence")
