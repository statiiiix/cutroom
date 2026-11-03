# The look: colours and fonts per video

The failure this file exists to stop: every edit comes out in the same fonts and the same colours. Left alone, a
model reaches for the same few faces (Space Grotesk, Inter, Montserrat, Poppins, Bebas Neue) and the same few
palettes (black and white with a coral or orange accent; near-black with a neon accent; a purple-blue gradient), on
every subject. That is habit, not a decision. So **every video gets a look chosen for that video**, and the choice is
written down and checked against the recent ones.

The method comes from the impeccable design skill (`/impeccable`: colour strategy, role-based palettes, the
reflex-font list and the calibration self-check), adapted to graphics that sit over footage.

## Contents
1. What is fixed, what is free
2. The look step
3. Colour: strategy first, then roles
4. Fonts: objects from the subject's world
5. The self-check
6. Contrast over footage
7. Using the look in film.js
8. Learning

## 1. What is fixed, what is free

**The brief wins.** Colours and fonts the user committed to are not re-decided. The profile's `look` settings say
which:

```json
"look": { "lock": ["accent", "captions"], "avoidRecent": 5, "ban": ["Montserrat"] }
```

- `lock` lists what stays the same in every video: `fonts` (both faces), `display` or `ui` (one face), `accent`
  (the brand accent), `palette` (every colour in `colors`), `captions` (caption font, colour and style). The
  defaults come from onboarding: a personal brand with set colours and fonts locks them; "pick for me" locks nothing.
- Whatever is **not** locked is chosen fresh for each video, and must differ from the last `avoidRecent` videos.
- Even when the accent is locked, the rest of the system is not: the panel and card tones, the field colour, the
  secondary roles and the display face (unless locked) still come from this video's subject and footage. A locked
  accent is one colour, not a whole look.
- `ban` lists faces or colours the user never wants. `look.py` never deals them.
- A product on screen always wears its own colours and logo (`graphics.productColors`), whatever the look.

## 2. The look step

Run it after the cut (step 4) and before the shotlist. It takes a minute.

```
$PY $SKILL/scripts/look.py footage                       # what the footage itself looks like
$PY $SKILL/scripts/look.py history                       # what the last videos used
$PY $SKILL/scripts/look.py deal --tags <subject words>   # strategy, hue zones, 3 font pairings
```

1. **Name the subject's world in one line.** Not the category ("a tech video") but the things in it: the tool, the
   material, the place, the era, the mood of the claim. "A Claude Code skill that edits video" → editing bays,
   timeline tracks, film leader, a cutting mat. "Why I quit my agency" → invoices, a closed laptop, a street at
   dusk. These are where colours and faces come from.
2. **Read the footage.** `look.py footage` prints the dominant colours of the cut (wall, shirt, skin, light) and
   how bright the caption band is. Decide in one sentence whether the graphics sit **in the footage's family**
   (tonal: they belong to the room) or are its **deliberate opposite** (a field that cuts against the shot).
   Either is fine; drifting between them is not.
3. **Take the deal.** `look.py deal` rolls a colour strategy, a few accent hue zones and three font pairings,
   skipping reflex fonts, banned faces and everything the recent videos used. The deal breaks the habit; it
   does not decide. Take a dealt option when it fits the subject, or replace it with something better that also
   isn't a repeat. `--tags` biases the font draw toward faces whose character matches the subject (tags are in
   `scripts/data/fonts.json`: `developer`, `editorial`, `warm`, `industrial`, `luxe`, `playful`, `retro`, `sport`,
   `condensed`, `heavy` and so on). `--script arabic` deals only faces that set Arabic.
4. **Write `look.json`** in the project root, with a one-line reason for each decision:
   ```json
   { "strategy": "committed",
     "scene": "warm tungsten room, black tee: graphics sit as the opposite, a cool field",
     "colors": { "text": "#F2F4F1", "ink": "#0F1A16", "muted": "#9DB0A6", "accent": "#3FD49A",
                 "card": "#F2F4F1", "panel": "#0F1A16", "field": "#1F5C46", "line": "#2A4A3D" },
     "fonts": { "display": "Hubot Sans", "ui": "Geist" },
     "why": { "display": "wide, engineered: matches a tool built for developers", "accent": "film-leader green, far from the last 3 videos" } }
   ```
5. **Check and apply.**
   ```
   $PY $SKILL/scripts/look.py check look.json      # contrast of every role pair, caption vs footage, freshness
   $PY $SKILL/scripts/look.py apply look.json      # fonts fetched, tokens written, recorded in the history
   $PY $SKILL/scripts/sync.py
   ```
   `check` fails on a contrast miss, a reflex face without a reason, a face or accent that repeats a recent video,
   or a missing strategy. Fix the look rather than arguing with the check.
6. **Tell the user in one line** ("Look for this one: a committed deep-green field, Hubot Sans with Geist: the
   wide face matches the developer subject"). If the profile wants the shotlist approved, put the look in that
   summary too.

## 3. Colour: strategy first, then roles

Pick a strategy before picking colours. Never pick the one the last two videos used (`deal` won't offer it).

| Strategy | On a video | Good for |
|---|---|---|
| **Restrained** | neutrals taken from the footage + one accent doing real jobs: the key word, the number that matters, the active state | calm explainers, personal stories, interviews |
| **Committed** | one saturated colour owns whole regions: the split-screen half, the big-type field, every card (30–60 % of the graphic area) | strong single claims, opinion pieces, launches |
| **Full palette** | 3–4 named roles: accent for emphasis, `accent2` for the "other side" (before/after, them/us), `accent3` for data | comparisons, lists, data, multi-product videos |
| **Drenched** | the graphic moments ARE the colour: full-bleed fields with type knocked out, footage collapsing into a card on it | high-energy shorts, hooks, list countdowns |

Then build **roles, not a bag of swatches**. Every colour on screen has one job:

| Token | Job |
|---|---|
| `--text` | light type over dark footage or panels |
| `--ink` | dark type on cards and light fields |
| `--muted` | secondary lines, labels, the inactive state (tinted from its surface, never a flat grey) |
| `--accent` | emphasis: the key word, the number, the active state, the button pressed |
| `--accent-2`, `--accent-3` | full-palette roles only: the other side, data series |
| `--card`, `--panel` | light and dark containers over the footage |
| `--field` | the large colour region for committed and drenched moments |
| `--line` | separators and outlines on panels |

How to choose the hues:
- **From the subject's world first**: the colours of the actual things in step 1 (a tool's brand colour belongs to
  `productColors`, not to the look; the look comes from the world around it).
- **From the footage second**: tonal (a deeper or brighter step of a colour already in the shot) or the deliberate
  opposite hue. `look.py ramp <hex>` prints an OKLCH tonal ramp of any colour, with its contrast on white and black,
  for building panels and fields that belong together.
- **Away from recent videos**: the deal skips accent zones within ~35° of the recent accents. Two zones are flagged
  as reflex (coral-orange, indigo-violet): they are allowed, but only with a written reason (or a locked accent).
- Work in OKLCH. Vary lightness for steps; ease chroma off near white and black (the ramp does). Tint neutrals
  toward the world's hue only when it makes the system cohere; neutral grey is fine when it serves the footage.
- When the accent is locked, a full or committed strategy uses a **tonal ramp of that accent** plus the world's
  neutrals rather than inventing a second brand colour.

## 4. Fonts: objects from the subject's world

Choose faces the way you'd choose props: from the subject's world, with a point of view, in the video's register.

- **Display face**: the voice of big type, numbers and lockups. It should have character that fits this subject:
  wide and engineered, condensed and urgent, a sharp high-contrast serif, a chunky retro face, a pixel face for a
  game. Short-form video is a Persuade surface: a face with a point of view beats a neutral one.
- **UI face**: captions, card text and labels. It must stay legible at 28–66 px on a phone over moving footage:
  open counters, sturdy weights, clear numerals. It can be the display face when that face is legible small (one
  family is often right), or a quieter companion.
- **Mono**: only when there is code, a terminal or data on screen. Monospace as a "techy" costume is banned.
- **Reflex faces** (in `fonts.json` → `reflex`: Space Grotesk, Inter, Montserrat, Poppins, Bebas Neue, Anton,
  Oswald, DM Sans, Outfit, Plus Jakarta Sans, Syne, Fraunces, Playfair Display, Manrope, Sora and the rest) mean you
  stopped looking. Using one needs a reason no other face could satisfy, written in `why`. A subject association is
  never that reason: tech wanting a mono, books wanting a serif, fitness wanting a condensed sans are exactly the
  associations to break. A locked brand face is a reason.
- Every face in the pool is on Google Fonts, so `get_font.py` fetches it. A face outside the pool is fine: ask for
  the file if it isn't on Google Fonts.
- Pairing: the two faces must differ in a way you can name (serif display + sans UI, wide display + narrow UI, heavy
  display + light UI) or be one family. Two similar sans faces is the worst of both.

## 5. The self-check

AI-made edits cluster around a few looks whatever the subject:
- black and white with a coral, orange or terracotta accent, in a geometric grotesk
- near-black with one neon accent (green, cyan) and glowing edges
- a purple-to-blue gradient behind white type
- the "podcast clip" look: uppercase Montserrat or Bebas, a yellow or green active word, a thick black stroke
- warm cream, an italic serif display and a terracotta accent

Each is legitimate when the user's brand is exactly that. Where the look is free, landing on one means the check
failed. Ask: **could someone guess this look from the video's category alone, or from the last video?** If yes,
rework it until neither answer is obvious. Then run `look.py check`.

## 6. Contrast over footage

`look.py check` verifies these; look at the sheets anyway.

| Pair | Minimum |
|---|---|
| body text on a card or panel (`ink` on `card`, `text` on `panel`) | 4.5 : 1 |
| big type, numbers, the accent on its container | 3 : 1 |
| captions over the footage band (p10 and p90 brightness) | 3 : 1, or carried by a shadow / stroke / adaptive colour |
| text or ink on the field (at least one of them) | 3 : 1 |

Information carried by colour also needs a shape, a label or a position (a tick, a strike-through, a "before"
label), so it reads for colour-blind viewers and on a dim phone.

## 7. Using the look in film.js

- Use the tokens: `var(--accent)`, `var(--field)`, `var(--card)` and so on, and `var(--display)`, `var(--ui)`,
  `var(--mono)`. Never hard-code a hex in `film.js`, except a product's own colours in that product's moment.
- The strategy decides the dosage: a restrained video keeps the accent rare (rarity gives it force); a committed
  video lets the field own whole regions instead of scattering small accents; a full-palette video gives each role
  one stable meaning for the whole video.
- `window.PROJECT.look` has the look (strategy, colours, fonts) if a scene needs to branch on it.
- The review scores the look like everything else: "Style match" now includes "a look of its own" (no repeat of a
  recent video, no reflex face without a reason).

## 8. Learning

- "I love this look" → offer to lock the parts they mean (`look.lock`), and log it in the feedback log.
- "Never use that font / colour" → add it to `look.ban`, log it, and re-run the look step for this video.
- "Too colourful" / "too plain" → next deal, steer the strategy (restrained ↔ committed / drenched) and log it.
- `look.py history` is the memory across videos; never edit it by hand except to remove a test run.
