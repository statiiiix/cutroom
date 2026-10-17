# cutroom style profile: {{NAME}}

Created {{DATE}} · last updated {{DATE}}

This file is the user's editing taste. cutroom reads it before every edit and appends to the feedback log whenever
the user corrects something, so the next video starts closer to right. Edit it by hand any time.

## Settings

`new_project.py` reads this JSON block. Keep it valid JSON.

```json
{
  "format": "9x16",
  "fps": 30,
  "colors": { "text": "#ffffff", "accent": "#FD9364", "ink": "#0e0e0e", "card": "#ffffff", "panel": "#0e0e0e", "muted": "#9a9a9a" },
  "fonts": { "display": "Space Grotesk", "ui": "Space Grotesk" },
  "captions": { "mode": "plain", "maxWords": 3, "maxChars": 18, "size": 66, "weight": 600, "color": "#ffffff",
                "case": "none", "position": 0.745, "shadow": true, "stroke": 0, "accentKeywords": true },
  "cut": { "maxPause": 0.35, "keepPause": 0.16, "head": 0.08, "tail": 0.22, "removeFillers": false, "punchIns": true },
  "sound": { "music": "none", "sfx": ["whoosh"], "voice": "standard", "lufs": -14 },
  "graphics": { "density": "rich", "newThingEvery": [2, 4], "productColors": true },
  "workflow": { "confirmScript": true, "approveShotlist": true, "reviewRounds": 2 },
  "vocab": ["Claude", "Claude Code", "Codex"]
}
```

## Who and what

- What they make, for whom, on which platforms:
- Personal brand or client brands:
- Typical length:

## Look

- Colours and when to use each:
- Fonts:
- Captions:
- Motion graphics they love:
- Never do:

## Sound

- Music:
- Sound effects:
- Voice treatment:

## Editing rhythm

- Pauses, fillers, retakes:
- Punch-ins and jump cuts:
- Hook (first 2 s):
- Ending / call to action:

## Reference notes

What cutroom learned from the creators and videos the user named. Keep the grammar (pacing, cut rate, caption
behaviour, graphic types, framing), never their content, branding or catchphrases.

## Feedback log

One line per correction: `YYYY-MM-DD: what they said → what changes from now on`.
