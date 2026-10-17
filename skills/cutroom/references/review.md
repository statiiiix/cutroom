# Review: look before you show

The user should only ever see a cut you already watched and scored. Everything is judged from rendered pixels
(sheets, stills, the draft), never from the code.

## Each round

1. `sync.py && sfx.py && mix.py` (so the sound is current)
2. `render.mjs --sheet` (1 frame per second), plus `--sheet --every 0.5 --offset 0.1` for dense stretches. LOOK at
   `review/sheet.jpg` and `review/sheet_phone.jpg`.
3. `render.mjs --at …` for any moment you suspect (swaps, overlaps, the hook's first frame, the last frame).
4. Score 1–10 with evidence (timestamps):

| criterion | 8+ means |
|---|---|
| Hook | something readable and intriguing is on screen by 0.5 s, and the point lands by 2 s |
| Readability at phone size | every word readable at 360 px wide; nothing in the safe-zone red; captions never collide with graphics |
| Motion | springs, clean swaps, no double exposure, no pure fades, punch-ins that feel motivated |
| Variety and pacing | something new every 2–4 s (or the profile's rate), no pattern three times in a row, no dead air |
| Style match | the profile's colours, fonts, caption style, density and sound palette; the feedback log respected |
| Sound | voice clear, SFX on visual events only, allowed types only, −14 LUFS, no clipping |

5. Fix the 3 worst problems, verify each fix with a still, and log the round in `docs/review_log.md` (scores + fixes).

## When to stop

After `workflow.reviewRounds` rounds (default 2), or as soon as every score is ≥ 8. Don't keep polishing frame-level
nits: users notice the wait more than a 7→8 on polish. If one score is still at 7, ship it and name it in one line
("the comment box enters a little late; say if you want it earlier").

## Draft check

`render.mjs --draft`, then `review.py renders/draft.mp4`:
- `draft_safe.jpg`: nothing important in the red zones
- `draft_phone.jpg`: the whole film at phone size, 1 fps
- metrics: loudness about −14 LUFS, true peak ≤ −1, no black frames, no frozen footage (a frozen graphic hold is OK)
