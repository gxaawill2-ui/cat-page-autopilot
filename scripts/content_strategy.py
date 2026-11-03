"""Reversible zero-cost content pilot for NEW vacant slots only.

This module never deletes, moves or rewrites previously scheduled/native posts.
The daily four-post safety CAP is enforced separately by Meta remote_guard.
"""
import datetime as dt

START=dt.date(2026,11,4)
EXPERIMENT_END=dt.date(2026,11,17)
PILOT_SLOTS=("12:30","19:30")


def should_generate(day,slot):
    """Pre-existing inventory is still preserved by the caller's CAS/native locks."""
    return day < START or slot in PILOT_SLOTS


def caption_variant(day,slot,language):
    """Alternate *within the same clock slot across days*, not by language/slot."""
    if day < START or day > EXPERIMENT_END or slot not in PILOT_SLOTS or language=="ja":
        return "standard"
    return "short" if (day-START).days % 2 == 0 else "micro_story"


def caption_guidance(variant):
    if variant=="short":
        return (" Write caption as 3 brief lines with a specific setup and one clear "
                "unexpected funny reversal. No listicle or heading, no hashtags, no "
                "follow-bait, no generic inspirational message.")
    if variant=="micro_story":
        return (" Write caption as 5 to 7 short lines of an original tiny cat story, "
                "ending with one funny reversal or relatable emotional payoff. "
                "No hashtags, no follow-bait, no generic inspirational message.")
    return ""


def require_caption_format(caption,variant):
    if variant not in ("short","micro_story"):
        return
    lines=[line.strip() for line in caption.splitlines() if line.strip()]
    lower=caption.lower()
    if (variant=="short" and len(lines)!=3) or (variant=="micro_story" and not 5<=len(lines)<=7):
        raise ValueError("CAPTION_FORMAT_QA_FAILED; no image requested")
    if "#" in caption or any(s in lower for s in ("like and follow","share this post","按讚追蹤","請分享")):
        raise ValueError("CAPTION_SPAM_QA_FAILED; no image requested")
