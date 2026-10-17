# Revisions and incremental builds

Use `scripts/build.py` after the user has confirmed the transcript and the editor has prepared `edit/cuts.json`.
It does not choose takes, rewrite speech, change the profile, or approve a shotlist. The existing scripts remain
available for manual work. The onboarding and feedback loop are unchanged.

```sh
# Run with the Python environment selected at installation.
PY="${CUTROOM_HOME:-$HOME/.cutroom}/venv/bin/python"
"$PY" "$SKILL/scripts/build.py" --project videos/example --status
"$PY" "$SKILL/scripts/build.py" --project videos/example --to cut
"$PY" "$SKILL/scripts/build.py" --project videos/example --to mix
"$PY" "$SKILL/scripts/build.py" --project videos/example --draft
"$PY" "$SKILL/scripts/build.py" --project videos/example
```

The installed `scripts/cutroom` wrapper also accepts `build` and `status`. No shell configuration is modified;
use the wrapper's full path or add its directory to PATH yourself.

## What is reused

| Change | Work needed |
|---|---|
| No change | All completed stages are skipped |
| Caption words, placement, color, or film graphics | Synchronize data, render picture, mux |
| Music file or mix gain | Mix audio, mux; reuse picture |
| SFX cues | Synchronize, synthesize SFX, mix audio, mux; reuse picture |
| Cut boundaries or order | Cut footage, remap source words, synchronize and rebuild affected outputs |
| Source footage or output aspect ratio | Cut footage and rebuild affected outputs |
| Missing or externally changed generated output | Rebuild its owning stage and any outputs whose inputs changed |

The stages are `cut → sync → sfx/mix/picture → final`. Each stage fingerprints only its relevant inputs, code,
and outputs. Equal output content does not force unnecessary downstream work. Draft and final pictures are
tracked separately. File hashes are cached against size, timestamps and inode so unchanged frame sequences
do not need to be read in full for every revision.

`renders/picture.mp4` and `renders/picture_draft.mp4` contain the reusable video track. `renders/final.mp4` and
`renders/draft.mp4` are the delivery files. Audio-only changes do not capture Chromium frames again. A film that
uses `window.SFX`, `R.P.sfx`, or `PROJECT.sfx` to drive graphics correctly invalidates the picture when cues change.
For custom audio-reactive code that reads other audio files, use `--force` when those files change.

## Transcript and cut revisions

`transcribe.py` reuses an existing transcript when the source contents, model, language, vocabulary and script
are unchanged. It retains manual word corrections. Pass `--force` to re-infer deliberately; changing vocabulary
or model also re-infers. Keep using the normal script confirmation step after a new inference.

On a revised cut, the builder maps output words back through the previous timeline to the source transcript,
retains confirmed text substitutions, and places the words in the new order. Source transcripts must remain in
`transcripts/<clip-stem>.words.json`. If you already ran `plan_cuts.py --remap`, its timeline receipt prevents a
second remap. For the first build, prepare and correct words as usual; subsequent builds remember that timeline.
Insertions or deletions that change what was spoken still need an editor's timing judgment.

## Status, interruption and manual changes

`--status --json` returns a machine-readable list without modifying project files. Pending upstream work is
reported conservatively when its new outputs are not known yet. A normal build reevaluates each stage after
the preceding stage completes, so unchanged outputs can still be reused.

State lives in `<project>/.cutroom/build.json`, beside any existing `.cutroom/style.md` link. Writes are atomic;
a failed or interrupted stage is never marked complete. A per-project lock prevents two builders from writing
the same outputs concurrently. Restart the same command to continue. Do not delete the style profile when
clearing build state; removing only `build.json` makes the next build start fresh.

Use `--to cut`, `--to sync`, `--to sfx`, `--to mix`, or `--to picture` to stop after that stage. `--force` rebuilds
all applicable stages through the target. Manual script changes are detected from their resulting files.
Projects with no footage can omit `edit/cuts.json` and set `clips: []`; set `audio: false` for intentionally silent
graphics. This is how the bundled [gallery](../examples/gallery/README.md) renders without source media.

## Renderer interoperability

The renderer can be used independently:

```sh
node "$SKILL/scripts/render.mjs" --project . --video-only --output renders/picture.mp4
node "$SKILL/scripts/render.mjs" --project . --mux --source renders/picture.mp4 --output renders/final.mp4
node "$SKILL/scripts/render.mjs" --project . --range 3,6
```

Range previews include the matching audio interval when a mix exists. `--video-only` explicitly omits it.
`CUTROOM_CHROMIUM` may point to an existing browser executable for diagnostics; normal installs use the managed
Playwright browser. `CUTROOM_NODE` selects the Node executable used by the builder.
Run `--verify` before relying on a custom browser: full-browser compositor behavior can differ from the managed
headless shell. If verification fails, inspect `review/determinism/` and return to the managed browser.
