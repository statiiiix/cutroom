// Runnable component gallery. Every graphic uses the production R.components API.
// No footage, remote assets, fonts or audio required. See create.py and README.md.
(() => {
  const { scene, make, set, keep, W, H } = R;
  const C = R.components, L = R.layout.recipe('full', { captions: false });
  const wide = L.wide;
  const paper = '#eaf0f5', ink = '#182735', blue = '#2856e8';
  const background = (root, color) => make('div', `position:absolute;inset:0;background:${color};`, root);
  const inset = (r, n = .04) => R.layout.rect([n, n, 1 - n * 2, 1 - n * 2], r);
  const tm = (from) => ({ from: from + .15, to: from + 2.65 });
  const add = (name, from, color, build) => scene({ name, from, to: from + 3,
    build(root, S) { background(root, color); S.parts = build(root, from); },
    run(t, S) { S.parts.forEach((p) => p.run(t)); },
  });

  add('hook', 0, ink, (root, from) => [
    C.hook(root, { rect: inset(L.content, .035), lines: wide ? ['Give every word', 'a reason to stay.'] : ['Give every', 'word a reason', 'to stay.'],
      size: wide ? 151 : 114, body: 'Motion follows the thought.', bodySize: wide ? 43 : 38, timing: tm(from) }),
  ]);
  add('counter', 3, paper, (root, from) => [
    C.counter(root, { rect: inset(L.content, wide ? .10 : .03), label: 'Time back in your day', value: 42, suffix: ' min',
      size: wide ? 250 : 180, note: 'Less time arranging. More time making.', noteSize: wide ? 44 : 36,
      background: 'transparent', padding: 0, timing: tm(from), duration: 1.1 }),
  ]);
  add('checklist', 6, paper, (root, from) => [
    C.checklist(root, { rect: inset(L.content, wide ? .08 : .025), title: 'Make the edit easy to follow.',
      titleSize: wide ? 90 : 67, size: wide ? 47 : 40,
      items: [{ text: 'Start with the point', detail: 'Let the first line do the work.' },
        { text: 'Show what changes', detail: 'Use one graphic for one idea.' },
        { text: 'Leave room to read', detail: 'Pace the reveal around the voice.' }], timing: tm(from) }),
  ]);
  add('comparison', 9, paper, (root, from) => [
    C.comparison(root, { rect: inset(L.content, .025), direction: wide ? 'row' : 'column', timing: tm(from),
      before: { label: 'Before', title: 'Everything\nat once.', body: 'Five ideas compete for attention.', background: ink, color: 'var(--text)', size: wide ? 93 : 82 },
      after: { label: 'After', title: 'One idea.\nThen the next.', body: 'A sequence the viewer can follow.', size: wide ? 93 : 82 } }),
  ]);

  // The preview is an invented edit structure, never a recreation of somebody else's product.
  function editPreview(parent, { w, R }) {
    const area = make('div', 'position:absolute;inset:12%;display:flex;flex-direction:column;justify-content:center;gap:18px;', parent);
    const words = ['Keep the thought.', 'Cut the pause.', 'Let it land.'];
    const rows = words.map((v, i) => {
      const row = keep(make('div', `position:relative;padding:${w * .018}px ${w * .025}px;border-left:6px solid ${blue};background:#2c3b48;color:#f5f8fb;font:500 ${Math.min(w * .045, 46)}px/1.1 var(--ui);letter-spacing:-.025em;`, area));
      row.textContent = v;
      return row;
    });
    return { run(t) { rows.forEach((e, i) => { const a = R.hit(t, 12.30 + i * .20, 'heavy'); set(e, { x: 24 * (1 - a), o: R.clamp(a) }); }); } };
  }
  add('product', 12, paper, (root, from) => [
    C.product(root, { rect: inset(L.content, wide ? .07 : .025), name: 'A clearer edit', symbol: '↳', nameSize: wide ? 47 : 40,
      body: 'Give the important moments their own space.', bodySize: wide ? 43 : 35,
      preview: editPreview, previewBackground: ink, timing: tm(from) }),
  ]);

  function media(root, rect, title, body, from) {
    return C.info(root, { rect, title, body, background: '#c7d9e7', color: ink,
      size: Math.min(rect.w * .12, rect.h * .22), bodySize: Math.min(36, rect.w * .07),
      timing: tm(from), padding: Math.min(rect.w, rect.h) * .10 });
  }
  function caption(root, rect, from) {
    return C.label(root, { rect, text: 'Keep a clear caption band.', size: Math.min(39, rect.h * .47), padding: 10,
      radius: 0, background: 'transparent', color: ink, timing: tm(from) });
  }
  add('talking-head-layout', 15, paper, (root, from) => {
    const l = R.layout.recipe('talking-head');
    return [media(root, l.media, 'The speaker', 'Keep the face clear.', from),
      C.info(root, { rect: l.graphic, title: 'The point\ngoes here.', body: wide ? 'The graphic sits beside the speaker.' : 'The graphic sits below the face.',
        size: Math.min(l.graphic.w * .115, l.graphic.h * .22), bodySize: Math.min(38, l.graphic.w * .06), timing: tm(from) }),
      caption(root, l.caption, from)];
  });
  add('tutorial-layout', 18, paper, (root, from) => {
    const l = R.layout.recipe('tutorial');
    return [media(root, l.media, 'Show the action.', 'The screen gets the space it needs.', from),
      C.checklist(root, { rect: l.graphic, title: 'Guide the eye.', titleSize: Math.min(l.graphic.w * .13, l.graphic.h * .14),
        size: Math.min(38, l.graphic.w * .07), items: ['Find the moment', 'Show the change', 'Let it read'],
        padding: Math.min(l.graphic.w, l.graphic.h) * .08, timing: tm(from) }),
      caption(root, l.caption, from)];
  });
  add('two-speaker-layout', 21, paper, (root, from) => {
    const l = R.layout.recipe('two-speaker');
    return [media(root, l.speakers[0], 'The question', 'Speaker one', from), media(root, l.speakers[1], 'The response', 'Speaker two', from),
      C.label(root, { rect: l.graphic, text: 'Two perspectives. One conversation.', size: Math.min(52, l.graphic.w * .045, l.graphic.h * .24),
        timing: tm(from), background: ink, color: 'var(--text)', padding: l.graphic.w * .04 }),
      caption(root, l.caption, from)];
  });
  R.start();
})();
