# Format-aware layout recipes

`R.layout` adds normalized composition geometry to the existing runtime. Recipes are **starting points for editorial judgment**: check the actual face, source aspect, caption position and target platform UI. They do not detect people or crop footage automatically.

```js
const L = R.layout.recipe('talking-head');
// Pixel rectangles for this project's format:
L.media; L.face; L.graphic; L.caption; L.safe; L.content;
const graphic = R.components.info(root, {
  rect: L.graphic, title: 'Keep the point clear.',
  timing: {from: 2, to: 4.7},
});
// Captions may use the suggested band when approved:
cap.run(t, {y: L.caption.y});
```

## Geometry

`recipe(name, options)` returns `canvas`, `safe`, `content`, `caption`, `graphic`, `gap`, `wide`, `format` and recipe-specific rectangles. Every rectangle is `{x,y,w,h}` in pixels, ready for a component. `content` ends one gap above the caption band. Set `captions:false` to use the whole safe region for a silent/full-screen graphic. `safe` and `caption` overrides are normalized fractions of the canvas; `gap` is pixels.

| Format | Canvas | Safe area `(x,y,w,h)` | Caption band `(x,y,w,h)` |
|---|---|---|---|
| `9x16` | 1080 × 1920 | `.07,.08,.80,.72` | `.07,.735,.80,.065` |
| `16x9` | 1920 × 1080 | `.06,.07,.88,.85` | `.13,.83,.74,.09` |
| `1x1` | 1080 × 1080 | `.07,.07,.86,.82` | `.09,.80,.82,.09` |
| `4x5` | 1080 × 1350 | `.07,.07,.84,.79` | `.08,.785,.82,.075` |

The vertical safe area reserves the top 8%, bottom 20% and extra right edge for common social overlays. Other formats use proportionate margins. These defaults cannot guarantee clearance from every app's UI. A profile's existing caption position remains unchanged: pass a custom normalized band matching it, move the graphic, or explicitly approve moving the captions.

```js
const L = R.layout.recipe('full', {
  caption: {x: .08, y: R.P.captions.y / R.H, w: .80, h: .065},
});
```

## Recipes

| Name | Structure | Why it works |
|---|---|---|
| `full` | `graphic === content` | A generous single region keeps the message dominant. Disable the caption reservation for a full-screen interstitial. |
| `talking-head` | `media`, protected `face`, `graphic` | Portrait: footage above, graphic below. Landscape: speaker left, graphic right. The face box marks space to protect; it does not claim to locate the actual face. |
| `tutorial` | `media`, `sidebar === graphic` | Landscape: screen gets 68% of content width. Portrait/square: screen above, steps below. The action stays large while instructions occupy a separate area. |
| `two-speaker` | `speakers:[first,second]`, `graphic` | Landscape: two speakers side by side. Portrait/square: stacked speakers. A shared takeaway band below connects both views, with captions further down. |

These recipes choose by aspect ratio, not CSS media queries. `wide` is true when width/height exceeds 1.2. `format` can be overridden when planning another output, but render a project with the matching `project.json.format`.

### Source footage

Recipe `media`/`speakers` rectangles describe destination viewports. Use cropped source frames with `object-fit:cover` or a custom image layer for tutorials/multiple speakers. The original `R.footage` still supports one full-canvas frame sequence. `R.frameFootage({card:1, rect:{x,y,w}})` preserves that full-canvas aspect and **does not** crop to the recipe's `h`; check the resulting height before using it. Keep the existing camera workflow when a recipe is only positioning graphics on full-screen footage.

### Custom layouts

`R.layout.rect(normalized, within?)` converts an array `[x,y,w,h]` or object `{x,y,w,h}` into a pixel rectangle. Default `within` is the runtime canvas; pass a recipe's content box to position relative to it. Coordinates are rounded to .01 px.

`R.layout.inset(pixelRect, padding)` insets by pixel padding. Padding can be a number or `[top,right,bottom,left]` with CSS-style defaults. `R.layout.grid(pixelRect,{columns:2,rows:1,gap:24})` returns equal row-major cells. The grid rejects invalid counts or a gap that leaves no cell space.

```js
const L = R.layout.recipe('full');
const cards = R.layout.grid(L.content, {columns: L.wide ? 2 : 1,
  rows: L.wide ? 1 : 2, gap: L.gap});
const note = R.layout.rect([0, .7, 1, .3], cards[0]);
```

## Visual reference

The [gallery source](../examples/gallery/film.js) uses the same eight beats in all four formats. Its last three beats isolate each layout without required footage. See [all format overviews](../examples/gallery/README.md#formats) and the [explanations and portrait stills](../examples/gallery/README.md#the-eight-beats). Generate local projects with `python3 skills/cutroom/examples/gallery/create.py /tmp/cutroom-gallery --format all`, then render and inspect the actual output.
