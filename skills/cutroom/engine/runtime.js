// cutroom runtime: a video is a pure function of time. window.seek(t) paints frame t, in any order.
//
// Rules this file enforces so renders are deterministic:
//   - every animated element is registered once (keep) and gets its props for THIS frame from set();
//     commit() rewrites every registered element each frame, so nothing leaks from the previous frame
//   - motion comes from closed-form springs (spring / track), never from timers, CSS transitions or rAF
//   - randomness only from rng(seed)
//   - 2D transforms only (3D / will-change create composited layers whose pixels depend on paint order)
//
// Loaded by film/index.html after film/data.js (window.PROJECT, window.WORDS, window.SFX).
(() => {
  const P = window.PROJECT || {};
  const SIZES = { '9x16': [1080, 1920], '16x9': [1920, 1080], '1x1': [1080, 1080], '4x5': [1080, 1350] };
  const [W, H] = SIZES[P.format || '9x16'];
  const FPS = P.fps || 30, DUR = P.duration || 10;

  // ------------------------------------------------------------ math
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, k) => a + (b - a) * k;
  const prog = (t, t0, t1) => clamp((t - t0) / (t1 - t0));     // linear 0→1, for typing / counters / slow pushes only
  const ease = {
    out: (x) => 1 - Math.pow(1 - x, 3),
    inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  };
  function rng(seed) {                                          // seeded PRNG (mulberry32 family)
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let z = Math.imul(a ^ (a >>> 15), a | 1);
      z ^= z + Math.imul(z ^ (z >>> 7), z | 61);
      return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ------------------------------------------------------------ springs
  // response = seconds for one natural period; damping = ratio (1 = critical, no overshoot)
  const PRESETS = {
    snap:   { response: 0.22, damping: 0.82 },   // buttons, chips, leading edges (tiny overshoot)
    smooth: { response: 0.40, damping: 0.88 },   // cards, panels, camera
    heavy:  { response: 0.50, damping: 1.00 },   // big type, lockups (no overshoot)
    bouncy: { response: 0.50, damping: 0.50 },   // playful accents only
  };
  const preset = (p) => (typeof p === 'object' ? p : PRESETS[p] || PRESETS.smooth);
  /** 0 → 1 spring released at tau = 0 (0 for tau < 0). */
  function step(tau, p = 'smooth') {
    if (tau <= 0) return 0;
    const { response, damping: z } = preset(p);
    const w = (2 * Math.PI) / response;
    if (z < 1) {
      const wd = w * Math.sqrt(1 - z * z);
      return 1 - Math.exp(-z * w * tau) * (Math.cos(wd * tau) + ((z * w) / wd) * Math.sin(wd * tau));
    }
    if (z === 1) return 1 - Math.exp(-w * tau) * (1 + w * tau);
    const s = Math.sqrt(z * z - 1), r1 = -w * (z - s), r2 = -w * (z + s);
    return 1 + (r2 * Math.exp(r1 * tau) - r1 * Math.exp(r2 * tau)) / (r1 - r2);
  }
  // time for a preset to cover half its travel: hits are led by this so they READ on the beat / word
  const halfCache = {};
  function lead(p = 'snap') {
    const k = typeof p === 'string' ? p : JSON.stringify(p);
    if (!(k in halfCache)) { let x = 0; while (step(x, p) < 0.5 && x < 2) x += 0.001; halfCache[k] = Math.max(x, 2 / FPS); }
    return halfCache[k];
  }
  const spring = (t, at, p = 'smooth') => step(t - at, p);
  /** spring that is visibly "there" ON time `at` (use for anything tied to a word or a sound) */
  const hit = (t, at, p = 'snap') => step(t - (at - lead(p)), p);
  /** value with several targets: keys [[time, value, preset?], ...]; each change is its own spring, so retargets keep momentum */
  function track(t, keys, p = 'smooth') {
    let v = keys[0][1];
    for (let i = 1; i < keys.length; i++) v += (keys[i][1] - keys[i - 1][1]) * step(t - keys[i][0], keys[i][2] || p);
    return v;
  }
  function trackXY(t, keys, p = 'smooth') {
    return { x: track(t, keys.map(([k, v, q]) => [k, v.x, q]), p), y: track(t, keys.map(([k, v, q]) => [k, v.y, q]), p) };
  }
  /** 1 between tIn and tOut with spring edges */
  const between = (t, tIn, tOut, pIn = 'snap', pOut = 'snap') => hit(t, tIn, pIn) - (tOut == null ? 0 : spring(t, tOut, pOut));

  // ------------------------------------------------------------ elements: keep() once, set() per frame
  const stage = document.getElementById('stage');
  stage.style.width = W + 'px'; stage.style.height = H + 'px';
  const KEPT = [];
  let FRAME = new Map();
  function make(tag, css = '', parent = stage, html = '') {
    const e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (html) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  /** register an animated element; base = props on frames nobody set() it. Hidden by default: keep(el, {o: 0}) */
  function keep(e, baseProps = {}) {
    if (!e.__kept) { e.__kept = true; e.__base = {}; e.__last = {}; e.__orig = {}; KEPT.push(e); }
    Object.assign(e.__base, baseProps);
    return e;
  }
  /** this frame's props: x y s sx sy r (deg) o hide clip filter text html style{} */
  function set(e, props) {
    if (!e) return;
    if (!e.__kept) keep(e);
    const cur = FRAME.get(e);
    FRAME.set(e, cur ? Object.assign(cur, props) : { ...props });
  }
  function commit() {
    for (const e of KEPT) {
      const p = { o: 1, ...e.__base, ...(FRAME.get(e) || {}) };
      const st = {};
      if (['x', 'y', 's', 'sx', 'sy', 'r'].some((k) => p[k] != null)) {
        const s = p.s ?? 1;
        st.transform = `translate(${(p.x || 0).toFixed(2)}px,${(p.y || 0).toFixed(2)}px) rotate(${(p.r || 0).toFixed(3)}deg) scale(${(s * (p.sx ?? 1)).toFixed(5)},${(s * (p.sy ?? 1)).toFixed(5)})`;
      }
      st.opacity = p.o >= 0.999 ? '' : String(Math.max(0, p.o).toFixed(4));
      st.visibility = p.hide || p.o <= 0.001 ? 'hidden' : '';
      if (p.clip) st.clipPath = p.clip;
      if (p.filter) st.filter = p.filter;
      if (p.style) Object.assign(st, p.style);
      for (const k of Object.keys(e.__orig)) if (!(k in st)) st[k] = e.__orig[k];   // un-set styles return to their original value
      for (const [k, v] of Object.entries(st)) {
        const custom = k.startsWith('--');
        if (!(k in e.__orig)) e.__orig[k] = custom ? e.style.getPropertyValue(k) : e.style[k];
        if (e.__last[k] !== v) { custom ? e.style.setProperty(k, v) : (e.style[k] = v); e.__last[k] = v; }
      }
      for (const key of ['text', 'html']) {
        const o = '__orig_' + key;
        if (key in p || e[o] != null) {
          if (e[o] == null) e[o] = key === 'text' ? e.textContent : e.innerHTML;
          const v = key in p ? p[key] : e[o];
          if (e.__last['_' + key] !== v) { key === 'text' ? (e.textContent = v) : (e.innerHTML = v); e.__last['_' + key] = v; }
        }
      }
    }
  }

  // ------------------------------------------------------------ scenes
  const SCENES = [];
  /** scene({ name, from, to, build(root, S), run(t, S) }): root is visible on [from, to) and run() is only called then */
  function scene(def) {
    const S = { ...def };
    S.root = keep(make('div', `position:absolute;left:0;top:0;width:${W}px;height:${H}px;overflow:hidden`), { hide: true });
    SCENES.push(S);
    return S;
  }
  const before = [], after = [];

  // ------------------------------------------------------------ footage: one image per source frame, swapped per seek
  // Video elements can't be seeked deterministically in headless Chrome; a JPG sequence can. seek() awaits decode().
  let FOOT = null;
  function footage({ dir = '../assets/foot', fps = P.footage?.fps || 30, count = P.footage?.count || 1, ext = 'jpg' } = {}) {
    const wrap = keep(make('div', `position:absolute;left:0;top:0;width:${W}px;height:${H}px;overflow:hidden;transform-origin:0 0`));
    stage.insertBefore(wrap, stage.firstChild);
    const img = make('img', `display:block;width:${W}px;height:${H}px;object-fit:cover`, wrap);
    const name = (i) => `${dir}/f${String(i).padStart(5, '0')}.${ext}`;
    img.src = name(0);
    FOOT = { wrap, img, fps, count, name, cur: 0 };
    before.unshift((t) => {
      const i = Math.min(count - 1, Math.max(0, Math.floor(t * fps + 1e-4)));
      if (i !== FOOT.cur) { FOOT.cur = i; img.src = name(i); }
    });
    return FOOT;
  }
  /**
   * Frame the footage this frame. zoom/focus: punch in around a point (the face). card: 0..1 mix toward a
   * rounded card at rect {x, y, w} (keeps the source aspect), e.g. to make room for a graphic below.
   */
  function frameFootage({ zoom = 1, focus = [W / 2, H * 0.36], card = 0, rect = { x: W * 0.27, y: 64, w: W * 0.46 }, radius = 44, shadow = true } = {}) {
    if (!FOOT) return;
    const ks = rect.w / W, s = lerp(zoom, ks, card);
    const x = lerp(focus[0] * (1 - zoom), rect.x, card), y = lerp(focus[1] * (1 - zoom), rect.y, card);
    set(FOOT.wrap, { s, x, y, clip: card > 0.002 ? `inset(0 round ${(radius * card) / s}px)` : null });
  }

  // ------------------------------------------------------------ type
  /** a masked line: words rise through it. opts { x, y, size, weight, color, font, align:'left'|'center', width, accent:[indices], accentColor } */
  function line(parent, text, o = {}) {
    const size = o.size || 120;
    const el = make('div', `position:absolute;left:${o.x || 0}px;top:${o.y || 0}px;${o.width ? `width:${o.width}px;` : ''}text-align:${o.align || 'left'};` +
      `overflow:hidden;white-space:nowrap;padding:0.1em 0.05em 0.2em;margin:-0.1em -0.05em 0;font:${o.weight || 700} ${size}px/${o.lh || 1} ${o.font || 'var(--display)'};` +
      `letter-spacing:${o.tracking ?? '-0.03em'};color:${o.color || 'var(--text)'};${o.css || ''}`, parent);
    const parts = text.split(' ');
    const words = parts.map((w, i) => {
      const s = make('span', `display:inline-block;${o.accent && o.accent.includes(i) ? `color:${o.accentColor || 'var(--accent)'};` : ''}`, el, w);
      if (i < parts.length - 1) el.appendChild(document.createTextNode(' '));
      return keep(s, { y: 0 });
    });
    keep(el);
    return { el, words, size };
  }
  /** words rise in (one time per word, or a start + stagger) and lift out at tOut. preset heavy = no overshoot (type) */
  function rise(t, L, times, tOut = null, o = {}) {
    const p = o.preset || 'heavy', stagger = o.stagger ?? 0.06, below = L.size * 1.5;
    L.words.forEach((w, i) => {
      const tin = Array.isArray(times) ? times[Math.min(i, times.length - 1)] : times + i * stagger;
      let y = below * (1 - hit(t, tin, p));
      if (tOut != null) y -= below * spring(t, tOut + i * stagger * 0.4, 'snap');
      set(w, { y, hide: y >= below * 0.999 || y <= -below * 0.999 });
    });
  }
  /** typewriter between t0 and t1 */
  function typeText(t, el, text, t0, t1) {
    const n = Math.floor(prog(t, t0, t1) * text.length + 1e-6);
    set(el, { text: text.slice(0, n) });
    return n;
  }
  /** card enter (rise + scale on a spring; opacity only rides along) and exit (lift + shrink). Returns visibility 0..1 */
  function pop(t, e, tIn, tOut = null, o = {}) {
    const a = hit(t, tIn, o.preset || 'smooth'), b = tOut == null ? 0 : spring(t, tOut, 'snap');
    const dy = o.dy ?? 70, s0 = o.s0 ?? 0.9;
    set(e, { x: o.x, y: (o.y || 0) + (1 - a) * dy - b * (o.dyOut ?? 60), s: s0 + (1 - s0) * a - 0.08 * b, o: clamp(a * 1.8) * (1 - b), hide: a < 0.002 || b > 0.998 });
    return a * (1 - b);
  }

  // ------------------------------------------------------------ captions (style comes from the user's profile)
  /**
   * captions(words, cfg) → { run(t, {y, hidden}) }
   * cfg: { mode: 'plain'|'highlight'|'box'|'reveal', maxWords: 3, maxChars: 18, gap: 0.3, size: 66, weight: 600,
   *        font, color: '#fff', activeColor, boxColor, case: 'none'|'upper', y: 1430, shadow: true, stroke: 0,
   *        keywords: { word: color }, strip: true (drop trailing , .) }
   */
  function captions(words, cfg = {}) {
    if (cfg.mode === 'off') return { chunks: [], run() {} };
    const c = { mode: 'plain', maxWords: 3, maxChars: 18, gap: 0.3, size: 66, weight: 600, color: '#fff', case: 'none', y: H * 0.745, shadow: true, stroke: 0, strip: true, ...cfg };
    const chunks = [];
    let cur = null;
    words.forEach((w, i) => {
      const prev = words[i - 1];
      const brk = !cur || cur.words.length >= c.maxWords || /[,.?!:;]$/.test(prev.w) || w.s - prev.e > c.gap || (cur.text + ' ' + w.w).length > c.maxChars;
      if (brk) { cur = { s: w.s, e: w.e, words: [], text: '' }; chunks.push(cur); }
      cur.words.push(w); cur.text = cur.words.map((x) => x.w).join(' '); cur.e = w.e;
    });
    const layer = make('div', `position:absolute;left:0;top:0;width:${W}px;height:${H}px;pointer-events:none`);
    const shadow = c.shadow ? 'text-shadow:0 2px 4px rgba(0,0,0,.45),0 4px 22px rgba(0,0,0,.5);' : '';
    const stroke = c.stroke ? `-webkit-text-stroke:${c.stroke}px ${c.strokeColor || '#000'};paint-order:stroke fill;` : '';
    const els = chunks.map((ch) => {
      const row = keep(make('div', `position:absolute;left:0;top:0;width:${W}px;text-align:center;white-space:nowrap;font:${c.weight} ${c.size}px/1.15 ${c.font || 'var(--ui)'};letter-spacing:-0.02em;color:${c.color};${shadow}${stroke}${c.case === 'upper' ? 'text-transform:uppercase;' : ''}`, layer), { o: 0 });
      const spans = ch.words.map((w, i) => {
        let txt = c.strip ? w.w.replace(/[,.]$/, '') : w.w;
        const key = txt.toLowerCase().replace(/[^a-z0-9']/g, '');
        const kc = c.keywords && c.keywords[key];
        const sp = keep(make('span', `display:inline-block;padding:0 0.12em;border-radius:0.22em;${kc ? `color:${kc};` : ''}`, row, txt));
        if (i < ch.words.length - 1) row.appendChild(document.createTextNode(' '));
        return { sp, w, kc };
      });
      return { row, spans, ch };
    });
    return {
      chunks,
      run(t, o = {}) {
        const y = o.y ?? c.y;
        els.forEach(({ row, spans, ch }, i) => {
          const next = chunks[i + 1];
          const end = next ? Math.min(next.s, ch.e + 0.6) : ch.e + 0.6;
          const live = !o.hidden && t >= ch.s - 0.06 && t < end - 0.06;
          if (!live) return set(row, { o: 0, hide: true });
          const a = hit(t, ch.s, 'snap');
          set(row, { o: 1, y: y + 22 * (1 - a) });
          spans.forEach(({ sp, w, kc }) => {
            const on = t >= w.s - 0.04;
            if (c.mode === 'highlight') set(sp, { style: { color: on && t < w.e + 0.05 ? (c.activeColor || 'var(--accent)') : (kc || c.color) } });
            else if (c.mode === 'box') set(sp, { style: on && t < w.e + 0.05 ? { background: c.boxColor || 'var(--accent)', color: c.boxText || '#000', textShadow: 'none' } : {} });
            else if (c.mode === 'reveal') set(sp, { o: on ? 1 : 0, y: on ? 10 * (1 - hit(t, w.s, 'snap')) : 0 });
          });
        });
      },
    };
  }

  // ------------------------------------------------------------ paint / seek
  function paint(t) {
    FRAME = new Map();
    for (const f of before) f(t);
    for (const S of SCENES) {
      const live = t >= S.from && t < S.to;
      set(S.root, { hide: !live });
      if (live && S.run) S.run(t, S);
    }
    for (const f of after) f(t);
    commit();
  }

  const fonts = [];
  function start() {
    for (const S of SCENES) S.build && S.build(S.root, S);
    window.FPS = FPS; window.DURATION = DUR; window.SIZE = [W, H];
    window.CUTS = (P.cuts || []).slice();                  // hard cuts in the footage (render never blends across them)
    window.seek = (t) => {
      paint(Math.max(0, Math.min(DUR - 1e-6, t)));
      return FOOT ? FOOT.img.decode().catch(() => 0) : Promise.resolve();
    };
    window.READY = (async () => {
      await Promise.all(fonts.map((f) => document.fonts.load(f).then((r) => { if (!r.length) console.warn('font not loaded: ' + f); })));
      await document.fonts.ready;
      await Promise.all([...document.images].map((i) => i.decode().catch(() => 0)));
      await window.seek(0);
      return true;
    })();
    // preview in a browser: open film/index.html?play and click (plays audio/mix.wav in sync)
    if (new URLSearchParams(location.search).has('play')) {
      const fit = () => { const k = Math.min(innerWidth / W, innerHeight / H); stage.style.transform = `scale(${k})`; stage.style.transformOrigin = '0 0'; };
      fit(); addEventListener('resize', fit);
      const audio = new Audio('../audio/mix.wav');
      document.body.addEventListener('click', () => (audio.paused ? audio.play() : audio.pause()));
      const loop = () => { window.seek(audio.currentTime % DUR); requestAnimationFrame(loop); };
      window.READY.then(loop);
    }
  }

  window.R = {
    P, W, H, FPS, DUR, stage, clamp, lerp, prog, ease, rng, PRESETS, step, lead, spring, hit, track, trackXY, between,
    make, keep, set, commit, scene, before, after, footage, frameFootage, line, rise, typeText, pop, captions, fonts, start,
  };
})();
