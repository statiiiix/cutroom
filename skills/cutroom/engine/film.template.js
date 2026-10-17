// FILM TEMPLATE: replace these example scenes with the approved shotlist.
// Times are seconds in the CUT footage. Build once; run(t) sets the complete frame.
// Layer order: footage first, scenes second, captions last. No timers or 3D transforms.
(() => {
  const { W, H, scene, track } = R;
  const C = R.components;
  const L = R.layout.recipe('talking-head');
  R.fonts.push('700 100px Display', '600 60px UI');

  R.footage();
  R.before.push((t) => R.frameFootage({
    zoom: track(t, [[-1, 1.08], [-0.05, 1, 'heavy']]),
    focus: [W / 2, H * 0.36],
  }));

  scene({
    name: 'hook', from: 0, to: 2.5,
    build(root, S) {
      S.graphic = C.hook(root, { rect: L.graphic, lines: ['Your hook', 'goes here.'],
        timing: { from: 0.15, to: 2.15 } });
    },
    run(t, S) { S.graphic.run(t); },
  });
  scene({
    name: 'clear-point', from: 2.5, to: 5,
    build(root, S) {
      S.graphic = C.info(root, { rect: L.graphic, title: 'One clear point.',
        body: 'Replace this with what the viewer needs to remember.',
        timing: { from: 2.65, to: 4.65 } });
    },
    run(t, S) { S.graphic.run(t); },
  });

  // Use the profile's caption position. L.caption gives a conservative alternate band.
  const cap = R.captions(window.WORDS || [], R.P.captions || {});
  const HIDE = [[0, 2.5]]; // hide captions while the hook says the same words
  R.after.push((t) => cap.run(t, { hidden: HIDE.some(([a, b]) => t >= a - 0.04 && t < b) }));
  R.start();
})();
