// Reusable graphics for the cutroom runtime. Build once, then call handle.run(t) in a scene.
// All motion is expressed through R.set/pop/hit; seeking backwards produces the same frame.
(() => {
  const R = window.R;
  if (!R) throw new Error('Load runtime.js before components.js');
  const { make, keep, set, clamp, hit, spring, pop } = R;
  const text = (tag, value, css, parent) => { const e = make(tag, css, parent); e.textContent = value ?? ''; return e; };
  const finite = (v, fallback) => Number.isFinite(v) ? v : fallback;
  const px = (v) => `${v}px`;
  const font = (size, weight = 500, family = 'var(--ui)', line = 1.2) => `font:${weight} ${size}px/${line} ${family};`;
  const bodySize = (w) => clamp(w * 0.045, 32, 48);
  function base(parent, o, defaults = {}) {
    const b = { x: o.x ?? 0, y: o.y ?? 0, w: o.width ?? 800, h: o.height ?? 360, ...o.rect };
    if (!(b.w > 0 && b.h > 0)) throw new Error('Component rect needs positive w and h');
    const pad = o.padding ?? Math.min(b.w, b.h) * 0.09;
    const root = keep(make('div', `position:absolute;box-sizing:border-box;left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px;` +
      `color:${o.color || defaults.color || 'var(--ink)'};background:${o.background ?? defaults.background ?? 'var(--card)'};` +
      `border-radius:${o.radius ?? 24}px;transform-origin:50% 50%;${o.css || ''}`, parent), { o: 0 });
    const timing = { from: 0, to: null, ...o.timing };
    const enter = (t, override = {}) => { const q = { ...timing, ...override }; return pop(t, root, q.from, q.to, { dy: o.dy ?? 38, s0: o.s0 ?? 0.97, preset: o.preset || 'heavy' }); };
    return { root, rect: b, pad, timing, enter };
  }
  const inner = (b, css = '') => make('div', `position:absolute;left:${b.pad}px;right:${b.pad}px;top:${b.pad}px;bottom:${b.pad}px;${css}`, b.root);
  function label(parent, o = {}) {
    const b = base(parent, o, { background: 'var(--panel)', color: 'var(--text)' });
    const e = text('div', o.text || 'Label', `display:flex;align-items:center;height:100%;${font(o.size ?? bodySize(b.rect.w), o.weight ?? 600)}letter-spacing:-.025em;`, inner(b));
    return { ...b, text: e, run(t, q) { b.enter(t, q); } };
  }
  function hook(parent, o = {}) {
    const b = base(parent, { radius: 0, padding: 0, ...o }, { background: 'transparent', color: 'var(--text)' });
    const size = o.size ?? Math.min(b.rect.w * 0.15, b.rect.h * 0.27);
    const lines = Array.isArray(o.lines) ? o.lines : String(o.text || 'Make the point.').split('\n');
    const wrap = inner(b, 'display:flex;flex-direction:column;justify-content:center;');
    const rows = lines.map((value) => {
      const clip = make('div', 'overflow:hidden;padding:.09em 0 .15em;margin:-.09em 0 -.15em;', wrap);
      return keep(text('div', value, `${font(size, o.weight ?? 700, o.font || 'var(--display)', o.lineHeight ?? 1.02)}letter-spacing:${o.tracking || '-.055em'};white-space:pre-wrap;`, clip));
    });
    const sub = o.body ? keep(text('div', o.body, `margin-top:${size * .35}px;max-width:34em;${font(o.bodySize ?? bodySize(b.rect.w), 400)}letter-spacing:-.02em;`, wrap), { o: 0 }) : null;
    return { ...b, rows, body: sub, run(t, q = {}) {
      const tm = { ...b.timing, ...q }; b.enter(t, q);
      rows.forEach((e, i) => { const a = hit(t, tm.from + i * (o.stagger ?? .08), 'heavy'); const z = tm.to == null ? 0 : spring(t, tm.to, 'snap'); set(e, { y: size * 1.2 * (1 - a - z), hide: a < .002 || z > .998 }); });
      if (sub) { const a = hit(t, tm.from + lines.length * .08, 'heavy'); set(sub, { y: 16 * (1 - a), o: clamp(a) }); }
    } };
  }
  function counter(parent, o = {}) {
    const b = base(parent, o), w = b.rect.w, h = b.rect.h;
    const wrap = inner(b, 'display:flex;flex-direction:column;justify-content:center;');
    const title = o.label ? text('div', o.label, `${font(o.labelSize ?? bodySize(w), 500)}letter-spacing:-.025em;margin-bottom:${h * .055}px;`, wrap) : null;
    const value = keep(text('div', '', `${font(o.size ?? Math.min(w * .25, h * .47), o.weight ?? 600, o.font || 'var(--display)', .95)}letter-spacing:-.065em;font-variant-numeric:tabular-nums;white-space:nowrap;color:${o.valueColor || 'var(--accent)'};`, wrap));
    const note = o.note ? text('div', o.note, `${font(o.noteSize ?? bodySize(w), 400)}letter-spacing:-.02em;margin-top:${h * .055}px;`, wrap) : null;
    const from = finite(o.from, 0), to = finite(o.value, 100), decimals = Math.max(0, Math.min(6, o.decimals ?? 0));
    const format = o.format || ((n) => `${o.prefix || ''}${n.toFixed(decimals)}${o.suffix || ''}`);
    return { ...b, title, value, note, run(t, q = {}) {
      b.enter(t, q); const tm = { ...b.timing, ...q }, at = q.countAt ?? o.countAt ?? tm.from, duration = Math.max(.001, o.duration ?? .8);
      const k = R.ease.out(R.prog(t, at, at + duration)); set(value, { text: format(from + (to - from) * k) });
    } };
  }
  function checklist(parent, o = {}) {
    const b = base(parent, o), w = b.rect.w, h = b.rect.h, wrap = inner(b, 'display:flex;flex-direction:column;');
    const title = o.title ? text('div', o.title, `${font(o.titleSize ?? w * .068, 650, 'var(--display)', 1.05)}letter-spacing:-.04em;margin-bottom:${h * .055}px;`, wrap) : null;
    const list = make('div', 'display:flex;flex:1;min-height:0;flex-direction:column;', wrap);
    const rows = (o.items || []).map((item, i) => {
      const v = typeof item === 'string' ? { text: item } : item;
      const row = keep(make('div', `display:flex;align-items:center;gap:${w * .035}px;flex:1;min-height:0;${i ? 'border-top:1px solid currentColor;' : ''}border-color:color-mix(in srgb,currentColor 15%,transparent);`, list), { o: 0 });
      const mark = keep(text('div', '✓', `display:flex;align-items:center;justify-content:center;flex:none;width:${w * .062}px;height:${w * .062}px;border-radius:50%;color:${o.markColor || 'var(--card)'};background:${o.accent || 'var(--accent)'};${font(w * .04, 700)};`, row), { o: 0 });
      const copy = make('div', 'flex:1;min-width:0;', row);
      text('div', v.text, `${font(o.size ?? bodySize(w), 550)}letter-spacing:-.025em;`, copy);
      if (v.detail) text('div', v.detail, `margin-top:.2em;${font(o.detailSize ?? bodySize(w) * .78, 400)}opacity:.65;`, copy);
      return { row, mark, at: v.at };
    });
    return { ...b, title, rows, run(t, q = {}) {
      b.enter(t, q); const tm = { ...b.timing, ...q };
      rows.forEach(({ row, mark, at }, i) => { const a = hit(t, at ?? tm.from + i * (o.stagger ?? .22), 'heavy'); set(row, { y: 18 * (1 - a), o: clamp(a) }); const m = hit(t, at ?? tm.from + i * (o.stagger ?? .22), 'snap'); set(mark, { s: .65 + m * .35, o: clamp(m) }); });
    } };
  }
  function info(parent, o = {}) {
    const b = base(parent, o), w = b.rect.w, h = b.rect.h, wrap = inner(b, 'display:flex;flex-direction:column;justify-content:center;');
    if (o.label) text('div', o.label, `${font(o.labelSize ?? bodySize(w) * .85, 500)}margin-bottom:${h * .07}px;opacity:.65;`, wrap);
    const title = text('div', o.title || 'One clear idea.', `${font(o.size ?? Math.min(w * .095, h * .22), o.weight ?? 650, o.font || 'var(--display)', 1.05)}letter-spacing:-.045em;white-space:pre-wrap;`, wrap);
    const body = o.body ? text('div', o.body, `${font(o.bodySize ?? bodySize(w), 400, 'var(--ui)', 1.3)}letter-spacing:-.015em;margin-top:${h * .07}px;max-width:35em;white-space:pre-wrap;`, wrap) : null;
    return { ...b, title, body, run(t, q) { b.enter(t, q); } };
  }
  function product(parent, o = {}) {
    const b = base(parent, o), w = b.rect.w, h = b.rect.h, wrap = inner(b, 'display:flex;flex-direction:column;');
    const head = make('div', `display:flex;align-items:center;gap:${w * .03}px;`, wrap);
    if (o.image) { const img = make('img', `width:${w * .10}px;height:${w * .10}px;object-fit:contain;flex:none;`, head); img.src = o.image; img.alt = ''; }
    else if (o.symbol) text('div', o.symbol, `${font(w * .07, 600, 'var(--display)')}color:${o.accent || 'var(--accent)'};`, head);
    text('div', o.name || 'Product', `${font(o.nameSize ?? bodySize(w), 600)}letter-spacing:-.025em;`, head);
    const preview = make('div', `position:relative;flex:1;min-height:0;margin:${h * .055}px 0;overflow:hidden;border-radius:${o.previewRadius ?? 12}px;background:${o.previewBackground || 'var(--panel)'};color:${o.previewColor || 'var(--text)'};`, wrap);
    // A custom preview builds into the same deterministic scene; it may return its own run(t).
    const custom = o.preview ? o.preview(preview, { w: w - b.pad * 2, h: h * .49, R }) : null;
    if (!o.preview) {
      const p = make('div', 'position:absolute;inset:12%;display:flex;align-items:center;justify-content:center;', preview);
      text('div', o.previewText || o.name || 'Product', `${font(w * .075, 600, 'var(--display)', 1.05)}letter-spacing:-.045em;text-align:center;`, p);
    }
    if (o.body) text('div', o.body, `${font(o.bodySize ?? bodySize(w), 400)}letter-spacing:-.02em;`, wrap);
    return { ...b, preview, run(t, q) { b.enter(t, q); if (custom && custom.run) custom.run(t, q); } };
  }
  function comparison(parent, o = {}) {
    const b = base(parent, { radius: 0, padding: 0, ...o }, { background: 'transparent', color: 'var(--text)' });
    const horizontal = o.direction ? o.direction === 'row' : b.rect.w / b.rect.h > 1.15;
    const gap = o.gap ?? Math.min(b.rect.w, b.rect.h) * .045;
    const w = horizontal ? (b.rect.w - gap) / 2 : b.rect.w, h = horizontal ? b.rect.h : (b.rect.h - gap) / 2;
    const sides = [o.before || { title: 'Before', body: 'Too many moving parts.' }, o.after || { title: 'After', body: 'One clear next step.' }].map((v, i) => {
      const card = info(b.root, { ...v, rect: { x: horizontal ? i * (w + gap) : 0, y: horizontal ? 0 : i * (h + gap), w, h }, background: v.background || (i ? 'var(--card)' : 'var(--panel)'), color: v.color || (i ? 'var(--ink)' : 'var(--text)'), size: v.size ?? Math.min(w * .12, h * .25), bodySize: v.bodySize ?? bodySize(w), padding: o.padding ?? Math.min(w, h) * .10, timing: { from: b.timing.from + i * (o.stagger ?? .12), to: b.timing.to } });
      return card;
    });
    return { ...b, sides, run(t, q = {}) { b.enter(t, q); const tm = { ...b.timing, ...q }; sides.forEach((v, i) => v.run(t, { from: tm.from + i * (o.stagger ?? .12), to: tm.to })); } };
  }
  R.components = Object.freeze({ label, hook, counter, checklist, info, product, comparison });
})();
