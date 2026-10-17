# Reusable graphics

Load `runtime.js`, `layouts.js`, `components.js`, then `film.js`. New projects already do this. Existing films keep the entire low-level `R` API; these modules only add `R.components` and `R.layout`.

Build a component once inside a scene, then call its `run(t)` on every live frame. Times are **absolute seconds in the cut**, matching words and SFX. The handle owns its DOM; entering, exiting and changing values use the production deterministic runtime.

```js
const L = R.layout.recipe('talking-head');
R.scene({
  name: 'time-saved', from: 5, to: 8,
  build(root, S) {
    S.graphic = R.components.counter(root, {
      rect: L.graphic, label: 'Time saved', value: 42, suffix: ' min',
      note: 'A result worth remembering.',
      timing: { from: 5.15, to: 7.65 }, duration: 0.8,
    });
  },
  run(t, S) { S.graphic.run(t); },
});
```

## Shared contract

Each constructor takes `(parent, options)` and returns `{root, rect, timing, run(t, override), …}`. Use `R.set(handle.root, …)` after `run` when a beat needs custom motion. The original `R.make`, `R.line`, `R.rise`, `R.pop` and other primitives remain available.

| Option | Meaning |
|---|---|
| `rect: {x,y,w,h}` | Pixel coordinates relative to parent. Use [layout recipes](layouts.md) or `R.layout.rect` to adapt formats. Alternative: `x,y,width,height`. |
| `timing: {from,to}` | Entry time and optional exit time. Default `from:0`, `to:null`. `run(t,{from,to})` overrides them for that frame. |
| `background`, `color` | CSS colors; default card/ink, except hook and comparison use a transparent wrapper. |
| `padding`, `radius`, `css` | Pixel inset, corner radius and optional static root styles. Hook/comparison default to zero inset. |
| `dy`, `s0`, `preset` | Entry travel, initial scale and runtime spring preset. Defaults: 38 px, .97, `heavy`. |

Fonts inherit `--display` and `--ui`; colors inherit `--text`, `--ink`, `--accent`, `--card`, `--panel`. Fonts, CSS variables and project styling still belong to the profile. Override a component's documented size/color when a specific shot needs it. A component never fetches fonts, footage or branding. The gallery supplies its own example palette separately.

Text is plain text. Newlines are supported in hook lines and info titles/bodies; `product.preview` is the explicit escape hatch for custom visuals. Avoid long prose: these are video graphics, not auto-layout documents. Choose a readable `size`/`bodySize`, shorten the copy or increase the rectangle when adapting language or fonts. Content is not silently clipped or reduced to unreadable text.

## Components

| Constructor | Content and controls | Use it for |
|---|---|---|
| `hook` | `lines:[]` or newline-separated `text`, optional `body`; `size`, `bodySize`, `font`, `weight`, `lineHeight`, `tracking`, `stagger` | Two to four short lines. Lines rise through individual masks without type overshoot. |
| `counter` | `label`, numeric `value`, optional numeric `from`, `prefix`, `suffix`, `decimals`, `note`; `size`, `labelSize`, `noteSize`, `valueColor`, `duration`, `countAt` | A quantity that lands on a spoken result. `format(n)` can format currencies or locales; keep it pure. `run(t,{countAt})` can retime counting independently. |
| `checklist` | `title`, `items:['Text', {text,detail,at}]`; `titleSize`, `size`, `detailSize`, `stagger`, `accent`, `markColor` | A process or short list. Absolute `item.at` times synchronize individual rows with words. Rows retain space before revealing, so nothing jumps. |
| `comparison` | `before` and `after` objects with info-card options; `direction:'row'|'column'`, `gap`, `stagger` | A clear change. Defaults to horizontal when the rectangle is wide, otherwise stacks. Each side has its own staggered entry and may have its own colors. |
| `info` | Optional `label`, `title`, optional `body`; `size`, `bodySize`, `labelSize`, `font`, `weight` | A single explanation or takeaway. Hierarchy comes from size and spacing. |
| `product` | `name`, optional local `image` or plain `symbol`, `body`; `nameSize`, `bodySize`, `previewText`, `previewBackground`, `previewColor`, `previewRadius`, `preview` | A tool or asset. Bring real logos/screenshots when naming a real product. The default text preview is intentionally generic. |
| `label` | `text`, `size`, `weight` | A short caption band, speaker label or one-line statement. Defaults to panel/text colors. |

### Custom product preview

The callback runs once during `build`. It receives a parent and `{w,h,R}`; `w` is the inner card width and `h` is an approximate preview allocation. Use absolute insets or percentage-based CSS for the actual preview area, which flexes around the name/body. Return an optional `{run(t)}` handle for animation. Assets referenced by `image` should live inside the project, and all custom animation follows the same runtime rules.

```js
R.components.product(root, {
  rect: R.layout.recipe('full').content,
  name: 'An original workflow', body: 'Show the action clearly.',
  preview(parent, { R }) {
    const note = R.keep(R.make('div',
      'position:absolute;inset:15%;font:600 52px/1.1 var(--display);', parent));
    note.textContent = 'The useful moment';
    return { run(t) { R.set(note, { x: 24 * (1 - R.hit(t, 1, 'heavy')) }); } };
  },
});
```

## Design decisions and examples

The [runnable gallery](../examples/gallery/README.md) uses **these same constructors**, including an original product preview. It works offline and has no required footage, audio or fonts. Its eight beats show when each graphic helps and how the recipes adapt composition. See the [source](../examples/gallery/film.js), [portrait stills and explanation](../examples/gallery/README.md#the-eight-beats), and [four-format overview](../examples/gallery/README.md#formats).

Use one idea per beat, size type before adding decoration, and leave time to read. On busy footage choose an opaque card. Hide captions when a graphic already says the same words. Run `render.mjs --verify` after changing a custom component and inspect settled **and entering/exiting** frames at phone width.
