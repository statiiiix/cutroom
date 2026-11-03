# Motion blueprint: the house rules for every graphic

This is the blueprint for motion graphics inside cutroom videos. It comes from the Motion Reel Kit (the
`/motion-reel` skill: its RULES, ENGINE, CAPTIONS and CRITIQUE files and the films made with it), translated from
product reels to graphics over footage and onto cutroom's `R` API. **Read it before writing the shotlist and again
before writing `film.js`.** Where the user's profile or feedback log says otherwise, the profile wins. Where a rule
here is stricter than [graphics.md](graphics.md), this file wins.

## Contents
1. Render contract
2. Rhythm
3. Springs
4. Enters, exits and transitions
5. Swaps and handoffs
6. Type on screen
7. Depth, camera and texture
8. Real UI, real logos
9. Adaptive captions (house recipe)
10. Banned
11. Critique: the fresh-eyes loop and 16 failure modes

## 1. Render contract

- The film is a pure function of time. `window.seek(t)` paints frame t, in any order, cold or after any other frame.
- In render mode there are no CSS transitions or animations, no `setTimeout`, no `requestAnimationFrame`, no `Date`,
  and no state carried between frames (never mutate a module variable inside `run()`).
- Randomness is seeded only: `R.rng(seed)`. Never `Math.random`.
- No `will-change`, `translate3d` or `translateZ(0)`. A composited layer caches its raster, so the same t paints
  differently depending on the previous frame (measured on a kit film: 9 of 12 probes differed, by up to 211/255 per
  pixel). `R.set` writes 2D transforms. If a shot truly needs CSS 3D (`perspective`, `rotateX`), run
  `render.mjs --verify` on it; if it fails, fake the depth in 2D (skew + scale + shadow) or draw it on a canvas.
- Verify determinism once per project: `node $SKILL/scripts/render.mjs --project . --verify`.

## 2. Rhythm

The grid is the speech. Every hit lands on the word that triggers it (times from `edit/words.json`); with a music
bed, cuts and big entrances also sit on the bar when a word allows it.

- **The hook reads in the first 2 s, and frame 0 is never empty.** Release the hook's first element at a negative
  time (`R.hit(t, -0.3)`) so frame 0 already reads, and start the camera punched in (1.08 → 1.0 on frame 0).
- **Something new every 2–4 s** (or the profile's `graphics.newThingEvery`). Nothing holds longer than about 4 s
  without a new element, a camera move or a state change.
- **Every held shot keeps moving**: a micro push of 1.00 → 1.03–1.08 on the footage, or a slow drift on a card.
- **The end card holds ≤ 2 s and is never static.** If the video loops, close on the frame it opens on.
- **Vary the pattern.** Never the same graphic type three beats in a row; vary size (chip → card → full split →
  big type) and position (chest band, top card, full frame).

## 3. Springs

Closed-form springs only, for everything that enters, exits or retargets. No easing curves for those.

| Preset | For | Overshoot |
|---|---|---|
| `heavy` | display type, logo lockups, big numbers | none |
| `smooth` | cards, panels, containers, the camera | ~0.5 % |
| `snap` | chips, buttons, pills, selections, indicators, leading edges | ~1.5 % |
| `bouncy` | mascots and playful stickers only, never UI or type | ~20 % |

- **Hits lead the word so they READ on it.** Use `R.hit(t, at)` (led by half the spring's travel) for anything with
  a word, a sound or a click. `R.spring` is for exits and motion with no sound. The audio stays on the word.
- **A value with several targets uses `R.track`**: one spring per change, each released at its own time, so a
  retarget keeps its momentum. Never restart a spring. Camera zoom, cursor paths, counters that retarget, a card
  that moves twice.
- **Indicators** (an underline, a selection, a tab bar sliding between items) use `R.indicator(t, stops)`: the
  leading edge rides a stiffer spring, so the bar stretches mid-move and settles.
- **Text inside a morphing box** (a pill that grows into a card, a button that becomes a toast) uses
  `R.swapAlpha(t, tIn, tOut)`: it enters just after the morph starts and is gone before the next one, so text never
  sits on a box that is changing shape underneath it.
- Linear progress (`R.prog`) only for typing, counters, slow pushes and scrolls.

## 4. Enters, exits and transitions

**Enters** (pick by what the element is):
- rise through a mask (type: `R.line` + `R.rise`)
- grow out of something: scale 0.8–0.9 → 1, with opacity snapping in within 4 frames (`R.pop`)
- type on (`R.typeText`, with a caret that hides once the line leaves)
- build: skeleton → content (a card's outline, then its rows tick in)
- card rise from the chest band
- wipe / reveal with `clip: R.inset(...)`

**Exits:**
- lift through the mask
- get covered by what replaces it
- get pushed past camera (scale up + drift off)
- collapse into what replaces it (a card shrinks into the chip it came from)
- a hard cut

**A pure opacity fade is never an enter or an exit.** Opacity only rides along. The one exception: a small sub-line
under a headline may fade.

**Transitions between graphic moments**: hard cut on the word, push-through, card rise, collapse-reveal, iris or
inset wipe, whip with overlap. **Never** crossfades, spins, glitches or light leaks.

## 5. Swaps and handoffs

These are where edits look cheap. Check every one in stills.

- **Swaps are sequential.** The outgoing element is fully gone before the incoming one lands: set the outgoing
  `tOut` from the incoming `tIn` minus the exit time (~0.14–0.25 s). At most one frame of overlap, with the outgoing
  one ≥ 95 % gone. No double exposure.
- **Masked words start ≥ 140 % of their size below the mask** (`R.rise` does this), so no glyph tops peek through
  the padding on the first frame.
- **Handoffs start under full cover.** An incoming scene that enters behind a wipe takes over exactly when the cover
  is complete: no blank frames mid-wipe, and the outgoing scene never vanishes early.
- **Nothing leaks.** Everything a scene registers is set on every frame of its window. Anything registered visible
  and never animated leaks outside its window.
- **Carets** hide the moment their line starts leaving.
- **Captions vs graphics**: hide captions (`hidden`) while a graphic shows the same words in big type, and move them
  (`y`) when a graphic takes their spot. Never let the two overlap.

## 6. Type on screen

The faces come from the video's look ([look.md](look.md)), never from habit.

- One display face and one UI face per video (a mono only where there is code or data).
- **Left-aligned at x ≥ 120 px** (at 1080 wide) for kinetic type and card titles. Centred type only for captions,
  single-word slams and numbers. Never a centred title alone on an empty field.
- Sentence case. Follow the user's punctuation habit (full stop or none). Accent colour on the key word or the
  second phrase only, never the whole line.
- Hero type and numbers 120–220 px at 1080 wide, card titles ≥ 54 px, body on cards ≥ 34 px, labels ≥ 28 px.
  **Scale the camera, not the font**, when something has to read bigger.
- Tracking: display -0.02 to -0.05 em, never tighter than -0.05 em; light text on dark gets slightly more tracking
  and weight than dark text on light.
- Everything that must be read passes the 360 px-wide phone check (`review/sheet_phone.jpg`).

## 7. Depth, camera and texture

- **Depth from perspective and shadow, never glow.** UI cards may settle from 12–22° of perspective toward ~3°, with
  deep, soft, offset contact shadows. Verify CSS 3D with `--verify`, or fake it in 2D.
- Cards over busy footage are solid (`--card` / `--panel` / `--field`) with a soft shadow. Shadows have an offset and
  a blur; a zero-offset coloured halo is glow, and glow is banned.
- **Camera**: start the hook punched in, punch in 1.05–1.09 on the strongest claims and on jump cuts, come back out
  on the next beat, and chain every move with `R.track`. Camera multipliers compound: if one scene multiplies zoom,
  divide it out downstream.
- **Split layouts**: collapse the footage into a top card (`frameFootage({card: 1})`) for big moments and re-block
  the graphic for the bottom half. Re-block per format; never letterbox 16:9 into 9:16.
- 9:16 keeps key content out of the platform UI zones: top 8–14 %, bottom 20 %, right 12 % of the lower half.

## 8. Real UI, real logos

- Use the real product UI and logo: a screenshot, the site's CSS colours and fonts, the official logo SVG. Never
  redraw UI that exists.
- When a piece exists only as a screenshot, rebuild it element by element in its own colours, icons and type, keep
  it simple, and say so in a comment in `film.js`.
- A product on screen wears its own colours (`graphics.productColors`). Everything else wears the video's look.

## 9. Adaptive captions (house recipe)

The house caption for a user's own talking-head footage, when the profile asks for adaptive captions: every pixel
of every letter takes the opposite polarity of the footage behind it, using **only colours from the video's look**
(the raw inverse hue reads as "a weird colour"). Dark backdrop (shirt, hair) → the accent; mid-dark → the light text
colour; light backdrop (wall, skin) → the ink. The colours keep changing as the subject moves.

- Case: natural sentence case. Groups of 1–3 words, ≤ ~16 characters; break on punctuation, pauses > 0.25 s and cuts;
  never end a group on a connector (and, the, to, a, of, that, or, by, is, how, your, my, like).
- Motion: `R.hit(t, g.t0, 'snap')`, scale 0.9 → 1, y +22 → 0, opacity snapping in within 4 frames. The next group
  replaces it with a hard cut. No exit animation, no pill, no shadow.
- Placement: centred around y ≈ 1300 of 1920 (over the chest, above the bottom 20 % zone). In a split layout, just
  below the footage card's top + 185.

Recipe: a caption scene with a canvas strip (`W × 190`, `getContext('2d', {willReadFrequently: true})`). Per frame:
draw the current footage frame behind the strip with the same zoom and offset the footage layer uses, blurred
3 px; per pixel take the backdrop luma L and blend `DARK·wd + MID·wm + LIGHT·wl` with
`wl = ss(0.40, 0.52, L)`, `wd = 1 − ss(0.16, 0.28, L)`, `wm = (1 − wd)(1 − wl)` (`ss` = smoothstep), where DARK,
MID and LIGHT are the look's accent, text and ink; then `globalCompositeOperation = 'destination-in'` and
`fillText` the group, so only the letters remain. The footage `<img>` must be decoded for frame t before the caption
samples it (wrap `window.seek` so it sets the frame's `src`, awaits `decode()`, then paints). Run `--verify` after
adding it.

## 10. Banned (unless the profile explicitly asks)

- a centred title on a gradient, or alone on an empty field
- everything fading in; fades as enters or exits
- corner labels, frame borders, section numbers as decoration
- glow on anything; neon halos; light leaks
- generic particle bursts, confetti, sparkles
- crossfades between moments, spins, glitches
- bounce or overshoot on UI and type
- emoji or unicode glyphs standing in for icons (use real SVG icons in one stroke weight)
- monospace as a "techy" costume when there is no code or data on screen
- gradient text
- dead time: a stretch with nothing new on screen

## 11. Critique: the fresh-eyes loop

The author is the worst judge of their own film. When a subagent tool is available, each review round spawns a
**fresh critic** that did not write `film.js`: hand it this file, [review.md](review.md), the project path and the
round number. It looks at every sheet, still and the draft, scores with evidence (timestamps, frame numbers), and
names the 3 worst problems with a concrete, testable fix each. Without subagents, critique in the critic's voice:
evidence first, no defending the code. A problem noted last round that is still visible cannot score higher than
last round.

Check each of these explicitly, every round:
1. Frame 0 is empty or the first word only reads at frame 3 or later.
2. A graphic reads late: it needs 3–6 frames after its word or sound to become readable (use `R.hit`).
3. The end card goes static for > 1.5 s, or the loop seam jumps.
4. The CTA, handle or URL is tiny at 360 px wide.
5. A scene cuts in over an unfinished wipe, so the outgoing one vanishes early or flickers.
6. Flat depth: cards read as stickers on the footage.
7. Empty zones: a container empty for a beat, a third of a 9:16 frame dead for > 1 s.
8. Double exposure at swaps: the outgoing lift still visible when the incoming line lands.
9. A caret lingers after its line leaves.
10. Glyph tops showing through the mask on the first frame of a slam.
11. An element exits before its scene moves, orphaning a sub-line.
12. Blank frames in a handoff: mid-whip, or after a wipe before the next element has size.
13. Type from another scene leaks outside its window.
14. Type crosses the face or busy UI while the camera moves.
15. A hold longer than ~4 s with nothing new.
16. Anything from the banned list, or a look that repeats a recent video (`look.py history`).

## Before you write film.js

- [ ] The shotlist names, per beat: time range, words, the graphic and its pattern, its enter and exit, its spring
  preset, the sound, and the 9:16 position.
- [ ] No pattern three times in a row; the hook reads at frame 0; something new every 2–4 s.
- [ ] The look is applied (`look.py apply`) and every colour on screen is one of its roles.
- [ ] Every swap has its `tOut` computed from the next `tIn`.
