# Onboarding: the style interview

Run this once, when there is no profile. The goal is a profile good enough that the first edit already looks like
theirs. Keep it brisk: about 5 rounds of at most 4 questions each, the recommended option first, and short options with a
one-line description. Skip any question the user already answered in their message or that their clips make
obvious (for example, the format of vertical footage). If they say "you pick" or "defaults", take the recommended
option and move on.

Before round 1, say in one sentence what's happening: "First edit, so I'll ask a few quick questions about your
style once and save them. Next time I'll skip straight to editing."

If the user dropped clips in the same message, start transcribing them in the background before the interview,
so the time isn't wasted.

## Round 1: setup

1. **What do you mostly make?** Talking-head shorts (Reels/TikTok/Shorts) · YouTube long-form · Podcast clips ·
   Tutorials / screen recordings → sets `format` (9x16 vs 16x9) and the pacing defaults.
2. **Who are the videos for?** My personal brand · My company / one brand · Several clients or brands → decides
   where the profile lives:
   - personal brand or one brand → `~/.cutroom/style.md` (global; every project uses it)
   - several brands → `~/.cutroom/profiles/<brand>.md`, one per brand. Ask the first brand's name. Each project
     links its profile: `mkdir -p <project>/.cutroom && ln -s ~/.cutroom/profiles/<brand>.md <project>/.cutroom/style.md`
3. **Typical length?** Under 30 s · 30–60 s · 1–3 min · Longer
4. **Your name or handle** (free text; used only in the profile title and any on-screen handle they ask for).

## Round 2: the look

1. **Colours.** Ask for their palette as hex codes or plain words ("black, white and a coral #FD9364"). Offer:
   Black + white + one accent (recommended; ask for the accent) · My brand colours (ask for them) · Match each video
   · Pick for me (then use near-black #0e0e0e, white, and one saturated accent that suits their footage).
   Store `colors.text`, `colors.accent`, `colors.ink`, `colors.card` and `colors.panel`. When something can be read two
   ways (for example "all black and white"), confirm it: it decides every frame.
2. **Fonts.** One display face for big type and one UI face for captions and cards (they can be the same).
   Options: Space Grotesk (recommended: modern, techy) · Inter (neutral) · Montserrat / Poppins (bold, creator
   style) · My own font (ask for the name, or the file if it isn't on Google Fonts).
3. **Product colours.** When a video is about another product (an app, a tool), should its part use that product's
   colours and logo? Yes (recommended) · No, always my palette

## Round 3: captions and graphics

1. **Caption style.** Plain words (recommended for a clean look) · Active word highlighted in the accent · Active word
   in a box/pill · Word-by-word pop-in · No captions → `captions.mode` = plain | highlight | box | reveal | off.
2. **Caption details** (one question with combined options, or let them type): size (small 56 / medium 66 / big 84),
   words per line (1–2 punchy / 3 / 4–6 sentence-style), case (normal / UPPERCASE), and position (lower third,
   recommended / centre / just under the face). Keywords in the accent colour? (yes, recommended).
3. **Motion graphics density.** Rich: something new every 2–4 s, with cards, counters, UI mockups and kinetic type
   (recommended for short-form) · Medium: a graphic every 5–8 s · Minimal: captions and punch-ins only →
   `graphics.density` and `graphics.newThingEvery`.
4. **What do you love or hate?** (free text, optional) Things they've seen and want (split screens, big numbers,
   emoji, B-roll, zooms) or never want (glow, spins, glitch, emoji, crossfades). Write it into the Look section.

## Round 4: sound and rhythm

1. **Music.** None (voice only) · Quiet background bed (ducked under the voice) · I'll supply tracks →
   `sound.music`.
2. **Sound effects.** Whooshes on transitions only · Subtle UI sounds (whooshes, pops, clicks) · Full sound design
   (adds ticks, thumps and dings) · None → `sound.sfx`, the allowed types. Tell them they can say "that sound is
   annoying" any time and you'll drop it for good.
3. **Pauses.** Tight: remove every pause over 0.3 s (recommended for short-form) · Natural: only pauses over 0.7 s
   · Keep everything → `cut.maxPause` 0.3 / 0.7 / 99. Also: cut "um / uh" and false starts? Yes (recommended) / No.
4. **Voice.** Clean it up (denoise, de-ess, EQ, compression; recommended) · Light touch · Leave it raw →
   `sound.voice` standard | light | off.

## Round 5: references (inspiration)

Ask: **"Any creators or specific videos whose editing style you want me to learn from?"** Options:
- Yes, I'll paste links (best: 1–3 links to videos whose editing they love)
- Yes, by name (ask which videos or which era; one link is worth a lot)
- No, use my answers

For each link, follow [reference-study.md](reference-study.md). Downloading uses yt-dlp, so ask once ("OK to
download these 2 videos locally just to study their editing?"). Write the findings into **Reference notes**. Keep
their grammar (cut rate, caption behaviour, graphic types, zoom habits, hook structure) and none of their branding,
catchphrases, logos or content.

## Round 6: workflow (one question round)

1. **Check the script before I build?** Yes (recommended: Whisper mishears brand names) · No, go straight to the edit
   → `workflow.confirmScript`
2. **Approve a shotlist before I build graphics?** Yes · No, surprise me and show me the draft (faster) →
   `workflow.approveShotlist`
3. **Quality vs speed.** 30 fps (recommended: fast, and talking-head footage is 30 fps anyway) · 60 fps (2× the
   render time) → `fps`
4. **Words I should always spell right** (free text: their name, brand, products, tools) → `vocab`

## Write the profile

```
$PY $SKILL/scripts/profile.py new <path> --name "<name>"
```
Fill the JSON block (valid JSON) and every prose section with what they said, in their words where possible. Then
show a short summary, for example:

> Saved your style to ~/.cutroom/style.md:
> 9:16 shorts, 30–60 s · black, white + #FD9364 · Space Grotesk · plain white captions, 3 words, lower third ·
> rich graphics every 2–4 s · whooshes only, no music · tight cuts, fillers out · learning from @creator's pacing.
> Say "change my style" any time.

Then continue straight into the edit they asked for.

## Changing the profile later

"Change my style", "update my captions" and similar: re-ask only the relevant round, update the profile, and log the
change in the feedback log.
