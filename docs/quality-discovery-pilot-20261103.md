# Daily Purr: zero-cost quality and discovery pilot (proposal, not live)

Prepared 2026-11-03 Asia/Taipei, for the existing `gxaawill2-ui/cat-page-autopilot` production. **Feature-branch only until tests and review pass.**

## Grounded baseline

- Page ID: `1346385028565797`.
- 2026-10-30 through 2026-11-01: ten real published posts, but no confirmed non-owner reactions, comments, shares or new follows. The Halloween reaction was the owner's own like **by owner testimony**; never label it outside engagement.
- Windsor `post_impressions` are cumulative impression events, not unique reach. Existing Graph engagement permission can fail; missing counts must remain unknown rather than manufactured zeros.
- No evidence yet that ChatGPT-produced images outperform Cloudflare or that English has improved international reach.

## What this PR changes (future unoccupied candidates only)

- Effective **2026-11-04**, the automatic AI generator attempts only **12:30 Traditional Chinese** and **19:30 English**. Its existing **2026-11-06 19:30 Japanese test** remains Japanese. 2026-11-03 is unchanged.
- The original **four posts/day hard cap** and Meta's >=90-minute cross-source safety spacing remain unchanged. Already scheduled/published/unknown reservations are not deleted, rescheduled, unlocked, or replayed; any already scheduled fifth-post exception is historical.
- Two formats, interleaved *within the same clock time* on alternate dates, 2026-11-04 to 2026-11-17: three-line short setup/reversal vs five-to-seven-line micro-story/reversal. Japanese posts are outside this comparison. Text fails closed if the requested structure/anti-spam check fails *before* image generation. The chosen format is durably recorded in new queue metadata.
- No new provider, model, subscription, cron, paid fallback, ad purchase, credit card or synthetic engagement. Free-plan expiry and image/Meta CAS safeguards stay in force. No Reels generation, external sharing or business account edits occur through this PR.

## Explicit acceptance and rollout

1. Run `python -m unittest discover -v -s scripts -p 'test_*.py'` and `python -m unittest discover -v -p 'test_*.py'` against THIS feature branch with **no** Cloudflare/Meta writes.
2. Validate new slot filtering, Japanese test, four-post cap, native/curated locks, quality hold and persisted caption-format metadata. Inspect latest genuine Meta Planner inventory first.
3. Only then merge PR and audit the next real unattended `event=schedule` run. Record its run ID, before/after vacancy, zero duplicate IDs and actual scheduled receipt if any. Do not call workflow success proof of posts without a Meta Post ID.
4. On the existing page, Work should check recommendation eligibility/Page quality and whether Insights can show non-follower reach; only add permissions via normal Meta official consent, no bypass.
5. Separately, Work may design **2–3 original three-scene, 10–15-second Reels/week**, with genuine distinct poses/actions and original sound/rights-cleared music. Do not use a single static image with a generic pan/zoom as a substitute. Preview each before posting. Reels count toward the 4/day cross-format cap, with safe spacing and true Meta Calendar checks.
6. Optional organic discovery: share only to relevant groups **where their rules permit Page participation**, at a respectful rate, with accurate disclosure. No bulk posting, follow/like exchanges, bot engagement or advertisements. Do not create an Instagram account without explicit user approval.
7. At **48 hours and seven days after publication**, record cumulative post impressions, reactions excluding known owner action, shares, comments, follower changes and actual non-follower reach only when available. For meaningful treatment comparison, use at least five sufficiently mature posts per arm, same-time/same-language as far as possible; otherwise mark inconclusive. Weekly review on 2026-11-08.
8. No pre-existing future Facebook posts may be modified, replaced or duplicated to implement this pilot. If tests or provider budgets fail, retain safe existing publishing and hold only new creation.

## Work division

- **This PR**: unattended content generation cadence, text structure and quality, tests.
- **Work / Meta UI**: confirm real production acceptance, inspect audience/recommendation settings, create and review actual Reels, inspect legitimate sharing placements, validate reach and truly external engagement.
- **Owner**: no repeated approval necessary for normal authorized Page posts, but official login/authorization/payment prompts remain under the owner's control; **no purchases authorized**.

Pilot revert: revert the PR; retain all historical publication/QA/receipt records. Do not retroactively send skipped time slots.
