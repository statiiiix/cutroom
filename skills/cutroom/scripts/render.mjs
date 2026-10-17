// Render a cutroom film: drives window.seek(t) in headless Chromium and pipes frames to ffmpeg.
//
//   node render.mjs --project <dir> --sheet [--every 1]      one frame per N s → review/sheet.jpg + review/sheet_phone.jpg
//   node render.mjs --project <dir> --at 1.2,3.4             stills → review/stills/t1.200.png
//   node render.mjs --project <dir> --range 3,6              a clip of seconds 3–6 (check motion) → renders/clip_3-6.mp4
//   node render.mjs --project <dir> --draft                  quick: 30 fps, CRF 22 → renders/draft.mp4
//   node render.mjs --project <dir>                          final: project fps (or --fps 60), CRF 16, H.264 yuv420p → renders/final.mp4
//   node render.mjs --project <dir> --mux                    put a new audio/mix.wav into renders/final.mp4 (or draft.mp4) without re-rendering
//   node render.mjs --project <dir> --verify                 determinism check (same t paints the same pixels in any order)
// Audio: audio/mix.wav is muxed in when present.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';

// playwright lives in ~/.cutroom/node (one shared install for Claude Code and Codex); a local install also works
let chromium;
for (const base of [path.join(process.env.HOME || '', '.cutroom/node/package.json'), import.meta.url]) {
  try { ({ chromium } = createRequire(base)('playwright')); break; } catch {}
}
if (!chromium) { console.error('playwright missing: run the cutroom installer (sh install.sh)'); process.exit(1); }

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(`--${k}`); return i < 0 ? d : argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true; };
const has = (k) => argv.includes(`--${k}`);
const ROOT = path.resolve(opt('project', '.'));
const P = JSON.parse(fs.readFileSync(path.join(ROOT, 'project.json'), 'utf8'));
const SIZES = { '9x16': [1080, 1920], '16x9': [1920, 1080], '1x1': [1080, 1080], '4x5': [1080, 1350] };
const [W, H] = SIZES[P.format || '9x16'];
const AUDIO = path.join(ROOT, 'audio/mix.wav');
const mk = (d) => fs.mkdirSync(path.join(ROOT, d), { recursive: true });
const run = (a) => { const r = spawnSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...a], { stdio: ['ignore', 'inherit', 'pipe'] }); if (r.status) throw new Error(String(r.stderr)); };

if (has('mux')) {
  const src = ['renders/final.mp4', 'renders/draft.mp4'].map((f) => path.join(ROOT, f)).find((f) => fs.existsSync(f)), tmp = src + '.tmp.mp4';
  if (!src) { console.error('nothing to mux: render first'); process.exit(1); }
  run(['-i', src, '-i', AUDIO, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', tmp]);
  fs.renameSync(tmp, src); console.log('muxed', path.relative(ROOT, src)); process.exit(0);
}

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf', '.wav': 'audio/wav', '.mp4': 'video/mp4' };
const server = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch({ args: ['--force-color-profile=srgb', '--disable-lcd-text', '--font-render-hinting=none'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) console.log('[page]', m.text()); });
page.on('pageerror', (e) => { console.error('[pageerror]', e.message); process.exitCode = 1; });
await page.goto(`http://127.0.0.1:${server.address().port}/film/index.html`);
await page.waitForFunction(() => window.READY, null, { timeout: 120000 });
await page.evaluate(() => window.READY);
const cdp = await page.context().newCDPSession(page);
const DUR = await page.evaluate(() => window.DURATION);
const shot = async (t) => {
  await page.evaluate((x) => window.seek(x), t);
  const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
  return Buffer.from(data, 'base64');
};
const t0 = Date.now();

if (has('sheet')) {
  const every = +opt('every', 1), dir = 'review/sheet'; mk(dir);
  for (const f of fs.readdirSync(path.join(ROOT, dir))) fs.unlinkSync(path.join(ROOT, dir, f));
  const times = []; for (let t = +opt('offset', 0.25); t < DUR; t += every) times.push(+t.toFixed(3));
  for (let i = 0; i < times.length; i++) fs.writeFileSync(path.join(ROOT, dir, `s${String(i).padStart(3, '0')}.png`), await shot(times[i]));
  for (const [name, tw, cols] of [['sheet', W > H ? 480 : 270, W > H ? 6 : 10], ['sheet_phone', 360, W > H ? 4 : 8]]) {
    const th = Math.round((tw * H) / W / 2) * 2, rows = Math.ceil(times.length / cols);
    const lab = `drawtext=text='%{eif\\:n*${every}+${+opt('offset', 0.25)}\\:d}s':x=8:y=8:fontsize=${name === 'sheet' ? 20 : 16}:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4,`;
    const args = (l) => ['-framerate', '1', '-i', path.join(ROOT, dir, 's%03d.png'), '-vf', `scale=${tw}:${th}:flags=lanczos,${l}tile=${cols}x${rows}:padding=6:color=0x202020`, '-frames:v', '1', '-q:v', '3', path.join(ROOT, `review/${name}.jpg`)];
    try { run(args(lab)); } catch { run(args('')); }
    console.log(`wrote review/${name}.jpg (${times.length} frames, 1 per ${every} s)`);
  }
} else if (has('at')) {
  mk('review/stills');
  for (const t of String(opt('at')).split(',').map(Number)) { const f = `review/stills/t${t.toFixed(3)}.png`; fs.writeFileSync(path.join(ROOT, f), await shot(t)); console.log('wrote', f); }
} else if (has('verify')) {
  const probes = Array.from({ length: 10 }, (_, i) => +(((i + 0.37) * DUR) / 10).toFixed(3)), cold = [];
  for (const t of probes) cold.push(await shot(t));
  let bad = 0;
  for (let k = probes.length - 1; k >= 0; k--) { await shot(probes[(k * 7 + 3) % probes.length]); if (!(await shot(probes[k])).equals(cold[k])) { bad++; console.log('differs at t =', probes[k]); } }
  console.log(bad ? `${bad}/${probes.length} probes differ: state leaks between frames` : `deterministic: ${probes.length}/${probes.length} probes identical`);
  if (bad) process.exitCode = 1;
} else {
  const draft = has('draft'), fps = +opt('fps', draft ? 30 : P.fps || 30);
  const [a, b] = has('range') ? String(opt('range')).split(',').map(Number) : [0, DUR];
  const out = has('range') ? `renders/clip_${a}-${b}.mp4` : draft ? 'renders/draft.mp4' : 'renders/final.mp4';
  mk('renders');
  const audio = fs.existsSync(AUDIO) && !has('range');
  const ff = spawn('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-c:v', 'png', '-framerate', String(fps), '-i', '-',
    ...(audio ? ['-i', AUDIO] : []), '-c:v', 'libx264', '-preset', draft ? 'veryfast' : 'medium', '-crf', String(opt('crf', draft ? 22 : 16)),
    '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
    ...(audio ? ['-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '320k', '-shortest'] : []), '-movflags', '+faststart', path.join(ROOT, out)],
  { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((ok, no) => ff.on('close', (c) => (c ? no(new Error('ffmpeg exit ' + c)) : ok())));
  const N = Math.round((b - a) * fps);
  for (let i = 0; i < N; i++) {
    const buf = await shot(a + i / fps);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 30 === 0) process.stdout.write(`\rframe ${i}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)} s   `);
  }
  ff.stdin.end(); await done;
  console.log(`\nwrote ${out}  ${N} frames @ ${fps} fps${audio ? ' + audio/mix.wav' : ' (silent)'}  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
await browser.close(); server.close();
