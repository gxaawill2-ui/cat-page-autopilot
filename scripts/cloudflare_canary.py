"""Single original generation acceptance. Feature branch only; zero Meta calls."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import auto_replenish as auto
import cloudflare_ai as cf

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feat/20261029-unattended-autopilot"


def persist(paths, message):
    auto.base.git("add", *[str(p.relative_to(ROOT)) for p in paths])
    auto.base.git("-c", "user.name=cat-canary[bot]", "-c",
                  "user.email=cat-canary@users.noreply.github.com", "commit", "-m", message)
    auto.base.git("push", "origin", "HEAD:" + BRANCH)


def run():
    if os.environ.get("GITHUB_REF") != "refs/heads/" + BRANCH:
        raise ValueError("Canary must use existing feature branch; no production write")
    if os.environ.get("CF_CANARY_ENABLED") != "true":
        raise ValueError("Canary not explicitly requested")
    cf.budget_gate(ROOT, dt.datetime.now(auto.TZ))
    _, key = cf.credentials()
    targets = list(auto.slots_to_fill(dt.datetime.now(auto.TZ)))
    if not targets:
        raise ValueError("No future normal slot")
    day, slot = targets[0]
    path = ROOT / "records/canary" / (str(day) + "-" + slot.replace(":", "") + ".json")
    previous = auto.base.read(path) if path.exists() else None
    if previous and previous.get("status")=="qa_failed_held" and previous.get("image_attempts")==2 and not previous.get("vision_response") and not previous.get("vision_diagnostic_attempted"):
        record=dict(previous)
        record.update(status="vision_diagnostic_armed_unknown",vision_diagnostic_attempted=True)
        auto.base.write(path,record)
        persist([path],"Record one same-image QA diagnostic; no text or image generation")
        jpg=(ROOT/record["image_path"]).read_bytes()
        if hashlib.sha256(jpg).hexdigest()!=record["image_sha256"]:
            raise ValueError("Diagnostic original image SHA mismatch")
        def save_diagnostic(raw):
            record["vision_response"]=raw
            auto.base.write(path,record)
            persist([path],"Preserve actual vision output; never infer PASS from job success")
        passed=auto.qa_image(jpg,record["content"]["scene"],key,raw_sink=save_diagnostic)
        record.update(status="qa_pass_needs_human_visual_acceptance" if passed else "qa_failed_held",image_qa=passed)
        auto.base.write(path,record)
        persist([path],"Save same-image vision verdict without any Facebook write")
        print(json.dumps(record,ensure_ascii=False))
        return
    retry_image = bool(previous and previous.get("status")=="qa_failed_held" and
                       previous.get("image_attempts",1)==1 and previous.get("image_sha256"))
    retry_caption = bool(previous and previous.get("status")=="caption_response_parse_failed" and
                         previous.get("caption_attempts")==1 and previous.get("image_calls_confirmed")==0)
    if previous and not (retry_image or retry_caption):
        raise ValueError("Existing canary intent; reconcile, never regenerate")
    record = {"slot": str(day) + "T" + slot, "status": "content_armed_unknown",
              "facebook_write_calls": 0, "retry_allowed": False,
              "started_at": dt.datetime.now(auto.TZ).isoformat(),
              "caption_attempts":previous["caption_attempts"] if retry_image else (2 if previous else 1),
              "image_attempts":2 if retry_image else 1, "previous_attempt":previous}
    auto.base.write(path, record)
    persist([path], "Persist original canary generation intent before inference")
    def save_raw(raw):
        record.update(status="caption_response_durable", generated_text=raw)
        auto.base.write(path,record)
        persist([path],"Persist actual model content before JSON parsing; never discard response")
    if retry_image:
        item,language=previous["content"],previous["language"]
    else:
        item,language=auto.content(day, slot, key,raw_sink=save_raw)
    record.update(status="image_armed_unknown", content=item, language=language)
    auto.base.write(path, record)
    persist([path], "Persist real AI caption before bounded image call")
    scene=item["scene"]
    if retry_image:
        scene += " Clean empty margins. Absolutely no signature, autograph, monogram, lettering, artist mark or watermark anywhere, including all corners."
    jpg = auto.make_image(scene, key)
    digest = hashlib.sha256(jpg).hexdigest()
    image_path = ROOT / "docs/assets" / (digest + ".jpg")
    image_path.write_bytes(jpg)
    record.update(status="jpeg_durable_qa_pending", image_sha256=digest,
                  image_path=str(image_path.relative_to(ROOT)),
                  image_model=cf.IMAGE, text_model=cf.TEXT, vision_model=cf.VISION)
    auto.base.write(path, record)
    persist([path, image_path], "Persist actual original canary JPEG before visual QA")
    def save_vision(raw):
        record["vision_response"]=raw
        auto.base.write(path,record)
        persist([path],"Persist actual vision response before quality decision")
    passed = auto.qa_image(jpg, item["scene"], key,raw_sink=save_vision)
    record.update(status="qa_pass_needs_human_visual_acceptance" if passed else "qa_failed_held",
                  image_qa=passed, completed_at=dt.datetime.now(auto.TZ).isoformat())
    auto.base.write(path, record)
    persist([path], "Persist actual canary vision decision; no Meta writes")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    import sys
    try:
        run()
    except Exception as exc:
        print("CANARY_STOP " + type(exc).__name__ + ": " + str(exc)[:180], file=sys.stderr)
        sys.exit(1)
