// FILM TEMPLATE: replace the example scenes with the approved shotlist. Times are seconds in the CUT footage.
// Layer order = call order: footage first, then scenes, then captions last (on top).
// Pure function of t: put everything you animate in run() via R.set / R.pop / R.rise. No timers, no Math.random.
(() => {
  const { W, H, set, make, keep, scene, pop, rise, line, hit, spring, track, clamp, lerp, ease, prog } = R;
  const S = window.PROJECT.style || {};
  R.fonts.push('700 100px Display', '600 60px UI');

  // ---------------------------------------------------------------- footage + camera
  R.footage();
  // punch-ins: a spring track (retargets keep momentum); `card` collapses footage into a top card for a split moment
  R.before.push((t) => {
    const zoom = track(t, [[-1, 1.08], [-0.05, 1.0, 'heavy'] /* , [4.6, 1.05], [7.0, 1.0] */]);
    const card = track(t, [[0, 0] /* , [18.0, 1], [21.8, 0] */]);
    R.frameFootage({ zoom, card, focus: [W / 2, H * 0.36] });
  });

  // ---------------------------------------------------------------- example: a hook lockup
  scene({
    name: 'hook', from: 0, to: 2.5,
    build(root, S2) {
      S2.title = line(root, 'Your hook here', { x: 0, y: H * 0.5, width: W, align: 'center', size: 110, accent: [1] });
    },
    run(t, S2) { rise(t, S2.title, [-0.3, 0.2, 0.4], 2.2); },
  });

  // ---------------------------------------------------------------- example: a card that pops on a word
  scene({
    name: 'card', from: 2.4, to: 5,
    build(root, S2) {
      S2.card = keep(make('div', `left:190px;top:${H * 0.5}px;width:700px;height:300px;background:var(--card);border-radius:40px;` +
        `display:flex;align-items:center;justify-content:center;font:700 90px var(--display);color:var(--ink)`, root, 'Card'), { o: 0 });
      S2.card.className = 'c';
    },
    run(t, S2) { pop(t, S2.card, 2.6, 4.7); },
  });

  // ---------------------------------------------------------------- captions (always last = on top)
  const cap = R.captions(window.WORDS || [], window.PROJECT.captions || {});
  const HIDE = [];                                   // [[t0, t1], ...] where a graphic already says the words
  R.after.push((t) => cap.run(t, { hidden: HIDE.some(([a, b]) => t >= a - 0.04 && t < b) }));

  R.start();
})();
