"""Direct Workers AI only. No billing upgrade, gateway fallback, or automatic retry."""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request

TEXT = "@cf/google/gemma-4-26b-a4b-it"
VISION = TEXT
IMAGE = "@cf/black-forest-labs/flux-1-schnell"
MODELS = frozenset((TEXT, IMAGE))
ORIGIN = "https://api.cloudflare.com/client/v4/accounts/"


def credentials():
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    key = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not re.fullmatch(r"[a-f0-9]{32}", account) or not key.strip():
        raise ValueError("Cloudflare credentials missing or invalid; no request sent")
    return account, key


def budget_gate(root, now):
    path = root / "state/cloudflare_free.json"
    if not path.exists():
        raise ValueError("CLOUDFLARE_FREE_PLAN_NOT_VERIFIED")
    policy = json.loads(path.read_text())
    required = ("verified", "workers_free", "no_paid_upgrade", "no_gateway_billing",
                "provider_hard_stop")
    if any(policy.get(k) is not True for k in required) or not policy.get("evidence_record"):
        raise ValueError("CLOUDFLARE_FREE_PLAN_NOT_VERIFIED")
    expiry = dt.datetime.fromisoformat(policy["valid_until"])
    if expiry.tzinfo is None or expiry <= now:
        raise ValueError("CLOUDFLARE_FREE_PLAN_EVIDENCE_EXPIRED")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Cloudflare redirect refused; credential not forwarded")


def request(endpoint, body, key):
    account, configured = credentials()
    if key != configured:
        raise ValueError("Cloudflare credential mismatch")
    if endpoint == "/chat/completions":
        if body.get("model") not in (TEXT, VISION):
            raise ValueError("Unreviewed Cloudflare text/vision model")
        suffix = "/ai/v1/chat/completions"
    elif endpoint == "/images/generations":
        if body.get("model") != IMAGE:
            raise ValueError("Unreviewed Cloudflare image model")
        prompt = body.get("prompt", "")
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 2048:
            raise ValueError("Invalid Cloudflare image prompt")
        suffix = "/ai/run/" + IMAGE
        body = {"prompt": prompt, "steps": 4}
    else:
        raise ValueError("Unreviewed Cloudflare endpoint")
    req = urllib.request.Request(ORIGIN + account + suffix, json.dumps(body).encode(),
        method="POST", headers={"Authorization": "Bearer " + key,
                                "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=150) as response:
            raw = response.read(18_000_001)
            if len(raw) > 18_000_000:
                raise ValueError("Cloudflare response exceeds size cap")
            result = json.loads(raw)
    except urllib.error.HTTPError as exc:
        # Never include request headers, raw response, token or an automatic retry.
        raise RuntimeError("CLOUDFLARE_HTTP_" + str(exc.code)) from None
    except urllib.error.URLError:
        raise RuntimeError("CLOUDFLARE_NETWORK_RESULT_UNKNOWN; no retry") from None
    if result.get("success") is False:
        codes = [str(e.get("code", "unknown")) for e in result.get("errors", [])
                 if isinstance(e, dict)]
        raise RuntimeError("CLOUDFLARE_REJECTED_CODES=" + ",".join(codes))
    if endpoint == "/images/generations":
        image = result.get("result", {}).get("image")
        if not isinstance(image, str) or not image:
            raise ValueError("Cloudflare did not return base64 image")
        return {"data": [{"b64_json": image}]}
    return result.get("result", result)
