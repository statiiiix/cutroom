# cutroom (for Codex and other agents)

This repo is the cutroom video-editing skill. The skill itself is `skills/cutroom/SKILL.md`: read it, and follow it
whenever the user wants a video edited. Scripts live in `skills/cutroom/scripts/` and run with
`~/.cutroom/venv/bin/python` (Python) or `node` (render.mjs). `sh install.sh` sets up everything.

When working ON cutroom itself (changing the engine or scripts):
- `engine/runtime.js` must stay deterministic: no timers, CSS transitions, rAF in render mode, Math.random, or 3D transforms.
- After engine changes, run `node skills/cutroom/scripts/render.mjs --project <a test project> --verify`.
- Keep SKILL.md under ~250 lines; detail goes in `skills/cutroom/references/`.
- `references/motion-blueprint.md` is the house motion blueprint and `references/look.md` the per-video colour and
  font method. Changes to graphics behaviour go there first; `scripts/data/fonts.json` faces must exist on Google Fonts.
