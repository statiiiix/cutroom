# Studying reference creators and videos

The user names creators or videos whose editing they like. You learn the **grammar**, not the content. Grammar
means how fast it cuts, how captions behave, what kinds of graphics appear and how often, how the camera punches
in, and how the hook and ending are built. Never copy logos, catchphrases, intros, music, characters or exact
layouts that identify that creator.

## Get the video

- A link: ask once for permission to download it locally for study, then
  `$PY $SKILL/scripts/reference.py <url> --out refs --name <short-name>`.
  If the download fails (private, region-locked, login), ask the user for the file or a screen recording.
- A name only: ask for 1–2 links ("which video of theirs is the style you mean?"). Creators change style over
  time, so a link beats a name.
- A file: `reference.py <file>` works the same.

## Read it (LOOK at the images, don't just read the JSON)

`refs/<name>/` holds `report.json`, `hook.jpg` (the first 3 s at 6 fps), `sheet.jpg` (every 0.5 s) and
`captions.jpg` (the lower half, every 0.5 s). Work out:

| | what to note |
|---|---|
| Pace | `cuts_per_min`, `median_shot_s`. Over 20 cuts/min is very fast; around 8 is calm. Note the jump-cut and punch-in habits. |
| Hook | what happens in the first 1–3 s: text slam, question, visual surprise, a cold open mid-sentence? |
| Captions | font feel (geometric / grotesk / rounded / serif), weight, case, size relative to the frame, words per line, active-word treatment (colour / box / scale / none), position, stroke or shadow, emoji |
| Graphics | types (big numbers, UI mockups, screenshots, stickers, arrows, B-roll, split screens), how often, where they sit (chest band, full screen, corners), their enter/exit motion |
| Colour | palette and accent usage (map it onto the USER's colours; don't adopt theirs unless the user asks) |
| Sound | music or not, SFX density, whooshes on cuts, risers into reveals (listen if you can; otherwise infer from cut rhythm) |
| Ending | CTA style, loop back to the start, end card or hard stop |

## Write it down

Add a block per reference to the profile's **Reference notes**, for example:

> **@creator, "video title" (link)**, 2026-10-17: 22 cuts/min, median shot 1.9 s, punch-in on every jump cut.
> Hook: a 3-word slam in the first 0.5 s. Captions: bold grotesk in uppercase, 2 words, white with the active word
> in yellow and a heavy shadow, centred just below the chin. Graphics: a screenshot card every ~3 s, sliding up from
> the bottom. No music, whoosh on every cut. Ends on a loop.
> **Take:** the cut rate, 2-word captions, punch-ins and screenshot cards. **Leave:** the yellow (use the user's
> accent) and the uppercase (the user wants normal case).

Then reconcile it with the user's own answers. Where they conflict, the user's answers win; ask if it matters. Update
the JSON settings the reference implies (for example `captions.maxWords: 2`, `cut.maxPause: 0.25`).
