# Daily Purr original Reels: current viral-format benchmark & implementation

Prepared 2026-11-04 (Taipei). Research examples are descriptive; view counts below are **third-party reported snapshots**, not independently confirmed current Meta insights. Historical *viral* sampling contains selection bias. **No guarantee of virality**.

## References researched (no third-party video or sound will be copied)

1. Aubrium cat niche, 1,300+ viral posts as of 2026-10-22: **stories 35%, skits 19%, POV 5%, 66% original environmental audio, 18% curiosity-gap hooks, 15% relatable hooks**. This is a benchmark of already-viral posts, not a statistically randomized success recipe. https://aubrium.com/blog/how-to-go-viral-in-cat
2. Aubrium 2026-11-03, 1,400+ curated viral samples: **funny cat moments** most common, with owner jokes and recognizable cat behavior also prominent. https://aubrium.com/blog/cat-reel-ideas
3. Trend roundup as of 2026-10-21: `Black Cat Clapping` short surprising motion (reported original 43.9M plays); `Knight Cat` cinematic ordinary-to-epic mismatch (reported ~1M likes); `Smalltown Boy Cats` synchronized repeatable dancing beat (reported 10.8M plays). These are trend *examples*, not footage/song licenses. https://jumponthetrend.app/trends/cats/
4. Facebook Meta's originality policy (2026-03): prioritize work created by the page; duplicated or lightly altered third-party footage is deprioritized. **Never use others' clips, screenshots, voices, music or logos as this channel's output**. https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/
5. Meta explains newer Reels recommendations are tuned to watch time and interests; no specific content format guarantees distribution. https://about.fb.com/news/2025/10/finding-sharing-reels-facebook-just-got-easier-more-fun

## Findings applied to our EXISTING original B-scheme animation

**Viral principle:** hook with visible, physical action before 1 second; minimal text; mini-story with comic turn; rhythm and custom sound; clean, satisfying final beat; avoid intros, image pan/zoom, unlicensed audio, imitation of named art or exact viral choreography.

For the already-saved `阿橘的深夜罐罐任務` original 15s master in `media/reels/2026-11-03-midnight/`:

| Edit time | Footage drawn from ORIGINAL source | Viewer effect |
| --- | --- | --- |
| 0–1 s | original source frames 220–243 (9.17–10.17s), can rolls and cat reacts | Immediate visual surprise / scroll stop |
| 1–6.375 s | source 91–219 (3.79–9.17s), cat creeps and reaches | Flashback, suspense, physically continuous paw movement |
| 6.375–12 s | source 220–354 (9.17–14.79s), can rolls, cat panics and plays innocent | Comedic punchline, same physical action returns and resolves |

Result: an original **12-second 1080×1920, 24fps** B-scheme short, constructed from the *actual continuous skeletal animation source frames*, not a slide show or a still-frame pan. Native original synthetic audio is re-cut to the same frame intervals. Top-level lightweight attention tags at beginning only; original subtitles retained.

Executable: `python3 scripts/viral_reel_edit.py --keys` to generate four QA previews, then `python3 scripts/viral_reel_edit.py` to render and produce `media/reels/2026-11-03-midnight/previews/ajiu-viral-hook-story-v1.mp4` locally in the runner. This code deliberately **does not publish** and does not modify existing 15s source/master or the official scheduler.

## Mandatory acceptance before distribution

- Run `python3 -m unittest discover -s scripts -p 'test_*.py' -v` on branch; all existing tests must pass. Include test_viral_reel_edit.py.
- The source atlas, background, font and original animate.py must be present; no re-generated substitutes.
- Inspect `--keys` and watch the FULL 12-second output at actual phone size; look for IK knee jumps, foot skating, contact with rolling can, face/eye stability, loop seam, subtitles safe zones, scene continuity. **Re-edit or hold** if quality fails. 24fps alone is not proof of smooth animation.
- Verify output metadata via ffprobe: 1080x1920, 24fps, 12s and original audio; compare captured source frame indices and the motion track. Recompress only within consented zero-cost workflow.
- Compare the existing 15-second B animation and 12-second edited Reel without altering any already published/scheduled/unknown content.
- Only after owner-quality review and Meta inventory/4-per-day/90-min/CAS safeguards pass, schedule at a FREE authorized future slot; if no slot, remain preview. No paid AI API, ad, card, engagement trade, new cron or automatic retry.
- Record canonical Meta published Reel ID **only after true Meta confirmation**. Do not republish original `The Box Test` or other previously published Reel.
- At 48h and day7, compare **within-reel watch time / completion / comments / shares and new followers**. Existing like by owner is not external interaction; do not fake audience reach. Because sample is tiny, a higher view count alone is not a causal success claim.

## Next-original series ideas based on the METHOD (not copying anyone's script)

- **小雪的財務審計**: dramatic close-up of the missing snack receipt → precise paw sorting → reveal she booked treats as essential spending (original office skit).
- **小夜的監視畫面**: starts with a suspicious shadow and moving tail → chase in moody hallway → innocent reveal of a rolling sock (mystery/POV).
- **咪寶的花園大作戰**: jumps into frame after a butterfly → nimble continuous chase → butterfly lands on his nose (cute action loop).

**Release policy: preview-only until QA passes; user asked to study and mimic methods, not to bypass quality or pre-existing Page reservations.**
