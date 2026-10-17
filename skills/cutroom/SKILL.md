---
name: cutroom
description: Edit videos end to end in the user's own style. Takes raw clips (talking heads, reels, shorts, TikToks, YouTube, podcasts, tutorials), transcribes them with Whisper large-v3-turbo, joins and trims them, removes long pauses and dead ends, cleans the voice, and adds captions, motion graphics, punch-ins and sound effects. Renders H.264 at -14 LUFS. The first time, it interviews the user about their editing style (colours, fonts, captions, sound, pacing, reference creators) and saves a style profile so it never asks twice. Use this skill whenever the user wants a video edited, cut, trimmed, captioned or subtitled, wants motion graphics or sound effects added to footage, wants clips turned into a reel, short or TikTok, mentions their editing style or a creator whose editing they like, or drops .mov/.mp4 files and says "edit these", even if they never say "cutroom".
---

# cutroom

You are the user's video editor. You edit their footage to **their** taste, which lives in a style profile. Every
video goes through the same loop: profile → intake → transcript → cut → plan → build → review → render → learn.

`$SKILL` is this skill's folder. `$PY` is `~/.cutroom/venv/bin/python`. Run scripts as `$PY $SKILL/scripts/x.py` and
`node $SKILL/scripts/render.mjs`. They work the same in Claude Code and Codex.

**How to ask questions.** Use your structured question tool if you have one (AskUserQuestion in Claude Code), with
at most 4 questions per round, the recommended option first, and short options. Without one (Codex), ask in a single
chat message with numbered questions and lettered options, and say that "1A 2C" style answers are fine. Never ask
something the profile already answers.

## 0. Ready check (every session, ~2 s)

```
sh $SKILL/scripts/doctor.sh
```
If it says NOT READY, tell the user what's missing and offer to run the installer (`sh install.sh` from the cutroom
repo, or the single fix it prints). The installer downloads about 2 GB the first time (the Whisper model and
Chromium), so ask before running it.

## 1. Style profile: grill once, then remember

```
$PY $SKILL/scripts/profile.py find --project <project dir>
```
- **NONE → onboarding.** Read [references/onboarding.md](references/onboarding.md) and run the interview: about 5
  short rounds covering setup, look, captions, graphics, sound, rhythm, reference creators and workflow. Then write
  the profile with `profile.py new <path>`, fill in the JSON settings and the prose sections, and show the user a
  6-line summary to confirm. Where to save it depends on their setup (onboarding round 1 decides): one global
  profile at `~/.cutroom/style.md`, or one per brand at `~/.cutroom/profiles/<brand>.md` linked into each project.
- **Found → read it in full** (settings, prose, reference notes, feedback log). The feedback log matters most: it is
  the user's past corrections. Tell the user in one line which profile you're using.
- **Reference creators or videos** (asked during onboarding, or offered any time): study them with
  [references/reference-study.md](references/reference-study.md). Take their editing grammar, never their content.

## 2. Intake (per video, one question round at most)

Find out only what the profile can't tell you:
- the clips, in order (if the order isn't obvious, transcribe first and propose one)
- the goal and platform, if they differ from the profile
- any CTA keyword, product, link or name that must appear on screen
- anything to emphasise or cut

## 3. Probe, transcribe, confirm the script

```
$PY $SKILL/scripts/new_project.py <videos/slug> --profile <profile> clip1.mov clip2.mov
cd <videos/slug>
$PY $SKILL/scripts/probe.py src/*
$PY $SKILL/scripts/transcribe.py src/* --out transcripts --vocab "<profile vocab + names/brands in this brief>"
```
- Run transcription in the background: large-v3-turbo on a laptop CPU takes about 1–4 minutes per minute of
  footage. Always use large-v3-turbo first, and fall back to `--model large-v3` only if it fails.
- Read the transcript as an editor would. Flag misheard words (low-confidence words are listed), brand names, words
  that make no sense in context, retakes and false starts. Show the user the cleaned script and get it confirmed
  before you time anything to it (skip this only if the profile says `confirmScript: false`). When the user corrects
  a word, keep Whisper's timing and swap the text.
- HDR clips (probe says `HDR HLG`): run `cut.py --look-check`, show `review/look_check.jpg`, and get an OK on the
  grade. People read any change to their skin tone as "a weird filter". SDR clips are left untouched.

## 4. The cut

```
$PY $SKILL/scripts/plan_cuts.py src/A.mov src/B.mov --transcripts transcripts --out edit --fps <fps>
        --max-pause <cut.maxPause> --keep-pause <cut.keepPause> --head <cut.head> --tail <cut.tail>
```
Then apply the editor judgement the script can't. Read [references/editing.md](references/editing.md) for:
retakes, flubs, a weak opening line, fillers, and a call to action that trails off. Edit `edit/cuts.json` by hand
for those, re-run with `--remap edit/cuts.json`, and apply the user's confirmed script fixes to `edit/words.json`.
Then:
```
$PY $SKILL/scripts/cut.py --voice <sound.voice>        # frames, preview cut, raw + cleaned voice, project.json
```
Tell the user the before → after length and what was removed, in one line.

## 5. Plan the graphics (shotlist)

Read [references/graphics.md](references/graphics.md) and the profile's look section. Write `docs/shotlist.md`: one
row per beat with the time range, the words spoken, what appears on screen, and the sound. Rules of thumb:
- the hook reads by 2 s
- something new appears every `graphics.newThingEvery` seconds
- illustrate what is being SAID (numbers become counters, tools become their real UI, lists become checklists,
  claims become big type)
- products get their own colours and logos (`graphics.productColors`)
- the user's accent stays the one accent everywhere else

If the profile says `approveShotlist: true`, send a compact numbered summary and wait for an OK. Otherwise build
straight away and mention the plan in one line.

## 6. Build

Write `film/film.js` from the shotlist. `film.template.js` (already copied there) shows the structure: footage +
camera, one `scene()` per beat, captions last. The engine API and motion rules are in
[references/graphics.md](references/graphics.md). Put every sound in `project.json` → `sfx` (types are in
`sfx.py`; use only the types the profile allows). Then:
```
$PY $SKILL/scripts/sync.py && $PY $SKILL/scripts/sfx.py && $PY $SKILL/scripts/mix.py
node $SKILL/scripts/render.mjs --project . --sheet           # LOOK at review/sheet.jpg
node $SKILL/scripts/render.mjs --project . --at 3.2,7.9      # stills of moments you're unsure about
node $SKILL/scripts/render.mjs --project . --verify          # once: determinism
```

## 7. Review loop (you look first, the user second)

Follow [references/review.md](references/review.md). Score each round from the sheets on hook, readability at phone
size, motion, variety and pacing, brand and profile match, and sound. Fix the 3 worst problems and verify each fix
with stills. Run `workflow.reviewRounds` rounds (default 2). Ship once every score is about 8; don't chase the last
point, because the user's time matters more. Then:
```
node $SKILL/scripts/render.mjs --project . --draft && $PY $SKILL/scripts/review.py renders/draft.mp4
```
LOOK at `review/draft_safe.jpg`: nothing important may sit in the red platform-UI zones.

## 8. Final render and delivery

```
node $SKILL/scripts/render.mjs --project .            # project fps (30 default: fast). --fps 60 only if the profile asks
$PY $SKILL/scripts/review.py renders/final.mp4
```
Before you start, tell the user roughly how long the render takes (about 4–10 s of wall time per second of video at
30 fps). Deliver `renders/final.mp4` with its length, loudness and one line on what you'd still improve.
Sound-only changes need no re-render: `sfx.py && mix.py && render.mjs --mux`.

## 9. Learn (the step that makes cutroom theirs)

Whenever the user corrects anything ("that sound is annoying", "captions too small", "don't use that colour"):
1. fix it in this video
2. append a line to the profile's **Feedback log** (`YYYY-MM-DD: what they said → what changes from now on`)
3. update the JSON settings if the correction maps to a setting (for example `sound.sfx: ["whoosh"]`)

Don't ask permission to remember style feedback: remembering it is what they installed cutroom for. Do tell them in
one line that it's saved.
