# Editing: the cut, the voice, the sound

## What plan_cuts.py does, and what it doesn't

It trims each clip's dead head and tail (silence before the first word and after the last), and shrinks every
pause longer than `maxPause` to `keepPause`. That covers about 80 % of a talking-head cut. You still need to make
these judgement calls by reading the transcript:

- **Retakes.** The same sentence said twice: keep the better (usually the last) take and drop the earlier one by
  splitting the segment in `edit/cuts.json`. Watch for "sorry", "let me say that again" and restarted sentences.
- **False starts and stumbles** ("I— I think", "the the"). Cut them out when the cut stays clean (the gap between
  words is over ~60 ms).
- **Fillers** ("um", "uh", "you know"). Whisper often leaves them out of the transcript but they're still in the
  audio. When `cut.removeFillers` is true, look for word gaps of 0.25 s or more that contain sound (the
  `silencedetect` output says they aren't silent) and cut them, but only where it doesn't make the speech sound
  chopped.
- **A trailing ending.** People often say the CTA, pause, and add "yeah" or shuffle. End 0.2–0.3 s after the last
  meaningful word.
- **Clip order.** When clips arrive in Finder order rather than story order, read all the transcripts and propose
  the order: hook → body → CTA → outro.

After hand edits, run `plan_cuts.py --remap edit/cuts.json`. Times in `cuts.json` are source seconds per clip, and
segments play in list order.

## Jump cuts

Every join in the cut is a jump cut (`project.json.cuts`). Make them feel intentional:
- change the framing on the cut (a punch-in of 1.05–1.08×, or back out) when `cut.punchIns` is on
- or land a graphic or caption change on it, so the eye has something new to follow
- a whoosh on a jump cut works if the profile allows whooshes; don't put a sound on every one

## The look of the footage

- SDR clips: leave them alone. No grade, no LUT, no "cinematic" filter.
- HDR iPhone clips (HLG): `cut.py` tone-maps them with hable at 203 nits plus gamma 0.92. Show `--look-check` first.
- Vertical source on a vertical canvas: cover-crop (cut.py does it). Horizontal source on 9:16: ask whether to
  crop to the face or to keep a split layout with graphics; never stretch.

## Voice

`cut.py --voice standard` runs a high-pass at 80 Hz, FFT denoise, −2.5 dB at 250 Hz (mud), +2.5 dB at 3.5 kHz
(presence), a gentle air shelf, a de-esser and 3:1 compression. `light` is gentler and `strong` is for noisy rooms.
If the user says the voice sounds "processed", "underwater" or "robotic", step down a level and log it.

## Sound design

- Only use the SFX types the profile allows (`sound.sfx`). Users often find clicks and ticks annoying: when in doubt,
  use fewer.
- A sound goes on a visual event: a card entering, a transition, a number landing. It never sits under speech
  without a visual reason.
- `whoosh` peaks on its cue time, so put the cue where the motion is fastest (the moment a card arrives or leaves).
- Music (if any): `audio/music.wav`, ducked under the voice by mix.py, about −20 dB under the voice. It must not
  fight the words.
- Loudness: −14 LUFS integrated with a true peak of −1 dBTP or lower (mix.py does it). Social platforms normalise
  to roughly this level.
