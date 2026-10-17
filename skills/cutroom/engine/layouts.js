// Normalized composition recipes. Coordinates are converted once; no per-frame DOM reads.
// Safe areas are conservative editorial defaults, not a promise about every platform's UI.
(() => {
  const R = window.R;
  if (!R) throw new Error('Load runtime.js before layouts.js');
  const FORMATS = {
    '9x16': { size: [1080, 1920], safe: [0.07, 0.08, 0.80, 0.72], caption: [0.07, 0.735, 0.80, 0.065] },
    '16x9': { size: [1920, 1080], safe: [0.06, 0.07, 0.88, 0.85], caption: [0.13, 0.83, 0.74, 0.09] },
    '1x1':  { size: [1080, 1080], safe: [0.07, 0.07, 0.86, 0.82], caption: [0.09, 0.80, 0.82, 0.09] },
    '4x5':  { size: [1080, 1350], safe: [0.07, 0.07, 0.84, 0.79], caption: [0.08, 0.785, 0.82, 0.075] },
  };
  const box = (r) => Array.isArray(r) ? { x: r[0], y: r[1], w: r[2], h: r[3] } : { ...r };
  const round = (v) => Math.round(v * 100) / 100;
  function rect(r, within = { x: 0, y: 0, w: R.W, h: R.H }) {
    const b = box(r);
    return { x: round(within.x + b.x * within.w), y: round(within.y + b.y * within.h), w: round(b.w * within.w), h: round(b.h * within.h) };
  }
  function inset(r, padding) {
    const p = typeof padding === 'number' ? [padding, padding, padding, padding] : padding;
    const [top, right = top, bottom = top, left = right] = p;
    return { x: r.x + left, y: r.y + top, w: Math.max(0, r.w - left - right), h: Math.max(0, r.h - top - bottom) };
  }
  function grid(r, { columns = 2, rows = 1, gap = 24 } = {}) {
    if (!Number.isInteger(columns) || columns < 1 || !Number.isInteger(rows) || rows < 1) throw new Error('grid rows/columns must be positive integers');
    const w = (r.w - gap * (columns - 1)) / columns, h = (r.h - gap * (rows - 1)) / rows;
    if (w <= 0 || h <= 0) throw new Error('grid gap leaves no space for cells');
    return Array.from({ length: columns * rows }, (_, i) => ({ x: r.x + (i % columns) * (w + gap), y: r.y + Math.floor(i / columns) * (h + gap), w, h }));
  }
  function recipe(name = 'full', opts = {}) {
    const format = opts.format || R.P.format || '9x16', f = FORMATS[format];
    if (!f) throw new Error(`Unknown layout format: ${format}`);
    const [w, h] = f.size, canvas = { x: 0, y: 0, w, h };
    const safe = rect(opts.safe || f.safe, canvas), caption = rect(opts.caption || f.caption, canvas);
    const gap = opts.gap ?? Math.min(w, h) * 0.025;
    const content = { ...safe, h: opts.captions === false ? safe.h : Math.max(0, caption.y - gap - safe.y) };
    const wide = w / h > 1.2;
    const out = { name, format, canvas, safe, content, caption, gap, wide, graphic: content };
    if (name === 'talking-head') {
      out.media = rect(wide ? [0, 0, 0.46, 1] : [0.12, 0, 0.76, 0.47], content);
      out.face = rect(wide ? [0.04, 0.04, 0.38, 0.60] : [0.16, 0.02, 0.68, 0.42], content);
      out.graphic = rect(wide ? [0.51, 0.10, 0.49, 0.80] : [0, 0.53, 1, 0.47], content);
    } else if (name === 'tutorial') {
      out.media = rect(wide ? [0, 0, 0.68, 1] : [0, 0, 1, 0.51], content);
      out.graphic = out.sidebar = rect(wide ? [0.72, 0, 0.28, 1] : [0, 0.56, 1, 0.44], content);
    } else if (name === 'two-speaker') {
      out.speakers = wide ? grid(rect([0, 0, 1, 0.70], content), { gap, columns: 2 }) : grid(rect([0, 0, 1, 0.70], content), { gap, columns: 1, rows: 2 });
      out.graphic = rect([0, 0.76, 1, 0.24], content);
    } else if (name !== 'full') throw new Error(`Unknown layout recipe: ${name}`);
    return out;
  }
  R.layout = Object.freeze({ formats: FORMATS, rect, inset, grid, recipe });
})();
