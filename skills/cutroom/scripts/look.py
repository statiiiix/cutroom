#!/usr/bin/env python3
"""The per-video look: colours and fonts chosen for THIS video, never by habit. See references/look.md.

  python look.py footage [--project .]           dominant colours of the cut footage + caption-band brightness
  python look.py history [-n 8]                  the looks of recent videos (~/.cutroom/looks.jsonl)
  python look.py deal [--project .] [--tags developer,warm] [--script arabic] [--seed N]
                                                 deals a colour strategy, accent hue zones and 3 font pairings,
                                                 skipping reflex fonts and everything the last videos used
  python look.py ramp "#2F6B4F"                  an OKLCH tonal ramp of one colour (for tonal panels and fields)
  python look.py check look.json [--project .]   contrast of every role pair + freshness against history
  python look.py apply look.json [--project .]   fetches the fonts, writes the tokens into film/index.html,
                                                 stores the look in project.json and records it in the history

look.json: {"strategy": "committed", "scene": "...", "colors": {"text","ink","muted","accent","accent2","accent3",
"card","panel","field","line"}, "fonts": {"display","ui","mono"?}, "why": {"display": "...", "accent": "..."}}
Anything the profile locks (settings.look.lock) comes from the profile and is not dealt.
"""
import argparse, datetime, glob, json, math, os, random, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from profile import settings

HIST = os.path.expanduser(os.environ.get('CUTROOM_LOOKS', '~/.cutroom/looks.jsonl'))
POOL = json.load(open(os.path.join(HERE, 'data/fonts.json')))
REFLEX = set(POOL['reflex'])
STRATEGIES = {'restrained': 'neutrals from the footage + one accent doing real jobs (key word, the number, active state)',
              'committed': 'one saturated colour owns whole regions: panels, fields, the split-screen half (30-60% of graphic area)',
              'full': '3-4 named colour roles (e.g. accent for emphasis, accent2 for the product side, accent3 for data)',
              'drenched': 'the graphic moments ARE the colour: full-bleed fields, type knocked out of them'}
# OKLCH hue zones (degrees). Two are where AI edits land by default: legal, but only with a reason.
ZONES = [(0, 'rose-red'), (30, 'coral-orange'), (60, 'amber'), (90, 'yellow-chartreuse'), (120, 'green'),
         (150, 'emerald-teal'), (180, 'cyan'), (210, 'sky'), (240, 'blue'), (270, 'indigo-violet'),
         (300, 'purple-magenta'), (330, 'pink')]
REFLEX_ZONES = {'coral-orange': 'terracotta / coral accent', 'indigo-violet': 'SaaS indigo-violet'}


# ------------------------------------------------------------ colour maths (sRGB <-> OKLCH, WCAG contrast)
def hex2rgb(h):
    h = h.strip().lstrip('#'); h = ''.join(c * 2 for c in h) if len(h) == 3 else h
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
def rgb2hex(c): return '#' + ''.join(f'{round(max(0, min(1, v)) * 255):02X}' for v in c)
def lin(v): return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
def gam(v): return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055

def oklch(h):
    r, g, b = (lin(v) for v in hex2rgb(h))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360

def from_oklch(L, C, H):
    def raw(c):
        a, b = c * math.cos(math.radians(H)), c * math.sin(math.radians(H))
        l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
    lo, hi = 0.0, C                                       # out of gamut: keep L and H, give up chroma
    if all(-1e-4 <= v <= 1 + 1e-4 for v in raw(C)): lo = C
    else:
        for _ in range(24):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if all(-1e-4 <= v <= 1 + 1e-4 for v in raw(mid)) else (lo, mid)
    return rgb2hex(tuple(gam(max(0, v)) for v in raw(lo)))

def lum(h): r, g, b = (lin(v) for v in hex2rgb(h)); return 0.2126 * r + 0.7152 * g + 0.0722 * b
def contrast(a, b): x, y = sorted((lum(a), lum(b)), reverse=True); return (x + 0.05) / (y + 0.05)
def zone(hue): return ZONES[int(hue % 360 // 30)][1]
def hue_gap(a, b): d = abs(a - b) % 360; return min(d, 360 - d)


# ------------------------------------------------------------ history and profile
def history(n=None):
    if not os.path.exists(HIST): return []
    rows = [json.loads(l) for l in open(HIST) if l.strip()]
    return rows[-n:] if n else rows

def project(pdir):
    p = os.path.join(pdir, 'project.json')
    return json.load(open(p)) if os.path.exists(p) else {}

def locks(S):
    # profiles from before the look step have no "look" block: whatever brand fonts / accent they name stays locked
    if 'look' in S: return set(S['look'].get('lock', []))
    return ({'fonts'} if any(S.get('fonts', {}).values()) else set()) | ({'accent'} if S.get('colors', {}).get('accent') else set())

def profile_settings(pdir):
    prof = project(pdir).get('profile')
    if not prof:
        from profile import find
        prof = find(pdir)
    return (settings(prof) if prof and os.path.exists(prof) else {}), prof


# ------------------------------------------------------------ commands
def cmd_footage(a):
    frames = sorted(glob.glob(os.path.join(a.project, 'assets/foot/*.jpg')))
    if not frames: sys.exit('no assets/foot/*.jpg yet: run cut.py first')
    import numpy as np
    pick = frames[::max(1, len(frames) // 24)][:24]
    W, Hh = 72, 128
    px, band = [], []
    cap_y = project(a.project).get('captions', {}).get('y')
    for f in pick:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-vf', f'scale={W}:{Hh}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                             capture_output=True).stdout
        im = np.frombuffer(raw, np.uint8).reshape(Hh, W, 3).astype(float) / 255
        px.append(im.reshape(-1, 3))
        if cap_y:                                          # the strip the captions sit on (±5 % of the height)
            H = {'9x16': 1920, '16x9': 1080, '1x1': 1080, '4x5': 1350}.get(project(a.project).get('format', '9x16'), 1920)
            r0, r1 = int((cap_y / H - 0.05) * Hh), int((cap_y / H + 0.05) * Hh)
            band.append(im[max(0, r0):r1].reshape(-1, 3))
    X = np.concatenate(px)
    rng = np.random.default_rng(7); C = X[rng.choice(len(X), 6, replace=False)]
    for _ in range(25):                                    # k-means, k = 6
        k = ((X[:, None] - C[None]) ** 2).sum(-1).argmin(1)
        C = np.array([X[k == i].mean(0) if (k == i).any() else C[i] for i in range(6)])
    share = np.bincount(k, minlength=6) / len(k)
    out = []
    for i in np.argsort(-share):
        h = rgb2hex(C[i]); L, Cc, Hh2 = oklch(h)
        out.append({'hex': h, 'share': round(float(share[i]), 3), 'L': round(L, 3), 'C': round(Cc, 3), 'h': round(Hh2), 'zone': zone(Hh2)})
    res = {'dominant': out, 'mean_luma': round(float((X @ [0.2126, 0.7152, 0.0722]).mean()), 3)}
    if band:
        B = np.concatenate(band) @ [0.2126, 0.7152, 0.0722]
        res['caption_band'] = {'luma_p10': round(float(np.percentile(B, 10)), 3), 'luma_p50': round(float(np.median(B)), 3),
                               'luma_p90': round(float(np.percentile(B, 90)), 3)}
    os.makedirs(os.path.join(a.project, 'review'), exist_ok=True)
    json.dump(res, open(os.path.join(a.project, 'review/footage_palette.json'), 'w'), indent=1)
    print('footage palette (share · hex · OKLCH L/C/h · zone):')
    for c in out: print(f"  {c['share'] * 100:4.1f}%  {c['hex']}  L{c['L']:.2f} C{c['C']:.2f} h{c['h']:>3}  {c['zone']}")
    print(f"mean luma {res['mean_luma']}" + (f" · caption band luma p10/p50/p90 {res['caption_band']['luma_p10']}/"
          f"{res['caption_band']['luma_p50']}/{res['caption_band']['luma_p90']}" if band else ''))
    print('→ panels and fields should either sit in the footage family (tonal) or be its deliberate opposite; say which.')


def cmd_history(a):
    rows = history(a.n)
    if not rows: return print('no looks recorded yet')
    for r in rows:
        c, f = r.get('colors', {}), r.get('fonts', {})
        print(f"{r.get('date')}  {r.get('project', '?'):<28} {r.get('strategy', '?'):<10} accent {c.get('accent', '?')} "
              f"({zone(oklch(c['accent'])[2]) if c.get('accent') else '?'}) · {f.get('display', '?')} / {f.get('ui', '?')}")


def cmd_deal(a):
    S, _ = profile_settings(a.project)
    look = S.get('look', {}); lock = locks(S); n = look.get('avoidRecent', 5)
    recent = history(n)
    seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1 << 30)
    R = random.Random(seed)
    print(f'deal (seed {seed}) · avoiding the last {len(recent)} looks · locked: {", ".join(sorted(lock)) or "nothing"}\n')

    # colour strategy: never the one the last two videos used, unless locked
    if 'palette' in lock: print(f"strategy: locked to the profile palette ({S.get('colors', {})})")
    else:
        used = [r.get('strategy') for r in recent[-2:]]
        opts = [s for s in STRATEGIES if s not in used] or list(STRATEGIES)
        s = R.choice(opts)
        print(f'strategy: {s.upper()}: {STRATEGIES[s]}')
        print(f"  (alternatives: {', '.join(o for o in opts if o != s) or 'none'})")

    # accent hue zones: away from recent accents; reflex zones only with a reason
    if lock & {'accent', 'palette'}: print(f"accent: locked to {S.get('colors', {}).get('accent')}")
    else:
        rh = [oklch(r['colors']['accent'])[2] for r in recent if r.get('colors', {}).get('accent')]
        free = [(h, z) for h, z in ZONES if all(hue_gap(h + 15, x) > 35 for x in rh)]
        R.shuffle(free)
        free.sort(key=lambda hz: hz[1] in REFLEX_ZONES)       # reflex zones last
        print('accent hue zones (OKLCH h°), first = dealt:')
        for h, z in free[:4]:
            print(f"  {z:<18} h {h}-{h + 30}" + (f'   ⚠ reflex zone ({REFLEX_ZONES[z]}): needs a reason' if z in REFLEX_ZONES else ''))
        if rh: print(f"  (recent accents at h {', '.join(str(round(x)) for x in rh)}: skipped)")

    # font pairings
    if 'fonts' in lock: return print(f"\nfonts: locked to {S.get('fonts')}")
    used = {r.get('fonts', {}).get(k) for r in recent for k in ('display', 'ui')}
    tags = set(t.strip() for t in (a.tags or '').split(',') if t.strip())
    seen, pool = set(), []
    for f in POOL['fonts']:
        if f['family'] in REFLEX or f['family'] in used or f['family'] in seen or f['family'] in look.get('ban', []): continue
        if a.script == 'arabic' and 'arabic' not in f['tags']: continue
        if a.script != 'arabic' and 'arabic' in f['tags']: continue
        seen.add(f['family']); pool.append(f)
    weight = lambda f: 1 + 3 * len(tags & set(f['tags']))
    def draw(cands, k=1):
        cands = list(cands); out = []
        for _ in range(min(k, len(cands))):
            f = R.choices(cands, [weight(c) for c in cands])[0]; out.append(f); cands.remove(f)
        return out
    disp = [f for f in pool if f['roles'] in ('display', 'both')]
    ui = [f for f in pool if f['roles'] in ('ui', 'both') and f['cat'] != 'mono']
    lockd, locku = S.get('fonts', {}).get('display') if 'display' in lock else None, S.get('fonts', {}).get('ui') if 'ui' in lock else None
    print('\nfont pairings (display / ui), each from a different family of form:')
    groups = [('serif-led', lambda f: f['cat'] == 'serif'), ('sans-led', lambda f: f['cat'] == 'sans'),
              ('expressive', lambda f: f['cat'] in ('display', 'mono') or not set(f['tags']).isdisjoint({'heavy', 'chunky', 'condensed', 'wide', 'pixel', 'retro'}))]
    R.shuffle(groups)
    for i, (name, test) in enumerate(groups, 1):
        d = lockd or (draw([f for f in disp if test(f)]) or draw(disp))[0]['family']
        u = locku or (d if R.random() < 0.25 and any(f['family'] == d for f in ui) else draw([f for f in ui if f['family'] != d])[0]['family'])
        tg = next((f['tags'] for f in pool if f['family'] == d), [])
        print(f"  {i}. {name:<11} {d} / {u}" + (f"   [{', '.join(tg)}]" if tg else ''))
    print('\nThe deal breaks habit; it does not decide. Pick (or replace) using the subject, the footage and the profile,'
          '\nwrite look.json with a one-line reason per choice, then run check and apply.')


def cmd_ramp(a):
    L0, C0, H0 = oklch(a.hex)
    print(f'{a.hex}: L {L0:.3f} C {C0:.3f} h {H0:.0f} ({zone(H0)})')
    for L in (0.97, 0.92, 0.84, 0.74, 0.64, 0.54, 0.44, 0.34, 0.24, 0.16):
        C = C0 * (1 - abs(L - 0.6) / 0.6) ** 0.7 if abs(L - 0.6) < 0.6 else 0.01   # chroma eases off near white and black
        h = from_oklch(L, max(C, 0.008), H0)
        print(f'  L{L:.2f}  {h}   on white {contrast(h, "#FFFFFF"):4.1f}:1   on black {contrast(h, "#000000"):4.1f}:1')


def cmd_check(a):
    L = json.load(open(a.look)); c = L.get('colors', {}); f = L.get('fonts', {}); bad = 0
    pairs = [('text', 'panel', 4.5), ('ink', 'card', 4.5), ('muted', 'panel', 3.0), ('accent', 'panel', 3.0), ('accent', 'card', 3.0),
             ('ink', 'accent', 3.0), ('text', 'field', 3.0), ('ink', 'field', 3.0)]
    print('contrast:')
    for x, y, need in pairs:
        if c.get(x) and c.get(y):
            r = contrast(c[x], c[y]); ok = r >= need
            if not ok and (x, y) in (('text', 'field'), ('ink', 'field')): ok = None   # one of the two only needs to pass
            print(f"  {'ok ' if ok else ('-- ' if ok is None else 'BAD')} {x} on {y}: {r:.1f}:1 (need {need})"); bad += ok is False
    if c.get('field') and max(contrast(c.get('text', '#fff'), c['field']), contrast(c.get('ink', '#000'), c['field'])) < 3:
        print('  BAD neither text nor ink reads on field'); bad += 1
    fp = os.path.join(a.project, 'review/footage_palette.json')
    if os.path.exists(fp) and json.load(open(fp)).get('caption_band'):
        b = json.load(open(fp))['caption_band']; cc = L.get('captions', {}).get('color') or c.get('text')
        if cc:
            worst = min(contrast(cc, rgb2hex((v, v, v))) for v in (b['luma_p10'], b['luma_p90']))
            capc = {**project(a.project).get('captions', {}), **L.get('captions', {})}
            held = capc.get('shadow') or capc.get('stroke') or capc.get('mode') == 'adaptive'   # a shadow, stroke or adaptive colour carries it
            tag = 'ok ' if worst >= 3 else ('warn' if held else 'BAD')
            print(f"  {tag} caption {cc} vs the footage behind it: worst {worst:.1f}:1"
                  + ('' if worst >= 3 else ' (carried by shadow/stroke: check the sheet)' if held else ' → shadow/stroke, a darker band, or adaptive captions'))
            bad += worst < 3 and not held
    print('freshness:')
    S, _ = profile_settings(a.project); lock = locks(S)
    for role in ('display', 'ui'):
        if f.get(role) in S.get('look', {}).get('ban', []):
            print(f"  BAD {role} {f[role]!r} is on the profile's ban list"); bad += 1
        if f.get(role) in REFLEX and not ({'fonts', role} & lock) and not L.get('why', {}).get(role):
            print(f"  BAD {role} {f[role]!r} is a reflex font: pick another or write why.{role}"); bad += 1
    recent = [r for r in history(S.get('look', {}).get('avoidRecent', 5)) if r.get('project') != project(a.project).get('name')]
    for r in recent:
        same = [k for k in ('display', 'ui') if f.get(k) and f.get(k) == r.get('fonts', {}).get(k) and not ({'fonts', k} & lock)]
        if same: print(f"  BAD {', '.join(same)} repeats {r.get('project')} ({r.get('date')})"); bad += 1
        if c.get('accent') and r.get('colors', {}).get('accent') and not lock & {'accent', 'palette'}:
            g = hue_gap(oklch(c['accent'])[2], oklch(r['colors']['accent'])[2])
            if g < 25 and abs(oklch(c['accent'])[0] - oklch(r['colors']['accent'])[0]) < 0.15:
                print(f"  BAD accent {c['accent']} is {g:.0f}° from {r.get('project')}'s {r['colors']['accent']}"); bad += 1
    if c.get('accent') and zone(oklch(c['accent'])[2]) in REFLEX_ZONES and not lock & {'accent', 'palette'} and not L.get('why', {}).get('accent'):
        print(f"  BAD accent sits in the {REFLEX_ZONES[zone(oklch(c['accent'])[2])]} reflex zone: write why.accent or move it"); bad += 1
    if not L.get('strategy'): print('  BAD no strategy named'); bad += 1
    print('PASS' if not bad else f'{bad} problem(s)'); sys.exit(1 if bad else 0)


def cmd_apply(a):
    L = json.load(open(a.look)); P = project(a.project); S, prof = profile_settings(a.project)
    lock = locks(S)
    cols = dict(L.get('colors', {})); fonts = dict(L.get('fonts', {}))
    if lock & {'palette'}: cols = {**cols, **S.get('colors', {})}
    elif 'accent' in lock and S.get('colors', {}).get('accent'): cols['accent'] = S['colors']['accent']
    for k in ('display', 'ui'):
        if {'fonts', k} & lock and S.get('fonts', {}).get(k): fonts[k] = S['fonts'][k]
    html_p = os.path.join(a.project, 'film/index.html'); html = open(html_p).read()
    for role in ('display', 'ui'):
        if not fonts.get(role): continue
        dest = os.path.join(a.project, 'assets/fonts', role)
        for old in glob.glob(dest + '.*'): os.remove(old)
        r = subprocess.run([sys.executable, os.path.join(HERE, 'get_font.py'), fonts[role], dest], capture_output=True, text=True)
        if r.returncode: sys.exit(f"font {fonts[role]!r}: {r.stderr.strip() or r.stdout.strip()}")
        fname = os.path.basename(r.stdout.strip().splitlines()[-1])
        html = re.sub(rf"(font-family: '{'Display' if role == 'display' else 'UI'}'; src: url\(\.\./assets/fonts/)[^)]+\)", rf'\g<1>{fname})', html)
    if fonts.get('mono'):
        r = subprocess.run([sys.executable, os.path.join(HERE, 'get_font.py'), fonts['mono'], os.path.join(a.project, 'assets/fonts/mono')], capture_output=True, text=True)
        if not r.returncode:
            fname = os.path.basename(r.stdout.strip().splitlines()[-1])
            if "font-family: 'Mono'" not in html:
                html = html.replace("@font-face { font-family: 'UI';", f"@font-face {{ font-family: 'Mono'; src: url(../assets/fonts/{fname}); font-weight: 100 900; }}\n  @font-face {{ font-family: 'UI';", 1)
                html = re.sub(r"--mono: [^;]+;", "--mono: 'Mono', 'SF Mono', Menlo, Consolas, monospace;", html, 1)
    for k, v in cols.items():
        tok = {'accent2': 'accent-2', 'accent3': 'accent-3'}.get(k, k)
        if re.search(rf'--{tok}: [^;]+;', html): html = re.sub(rf'--{tok}: [^;]+;', f'--{tok}: {v};', html, 1)
        else: html = html.replace('--line:', f'--{tok}: {v}; --line:', 1)
    open(html_p, 'w').write(html)
    P['look'] = {**L, 'colors': cols, 'fonts': fonts}
    if L.get('captions'): P['captions'] = {**P.get('captions', {}), **L['captions']}
    json.dump(P, open(os.path.join(a.project, 'project.json'), 'w'), indent=1)
    if not a.no_record:
        os.makedirs(os.path.dirname(HIST), exist_ok=True)
        name = P.get('name') or os.path.basename(os.path.abspath(a.project))
        rows = [r for r in history() if r.get('project') != name]
        rows.append({'date': datetime.date.today().isoformat(), 'project': name, 'profile': prof, 'strategy': L.get('strategy'),
                     'colors': cols, 'fonts': fonts})
        open(HIST, 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
    print(f"applied: {L.get('strategy')} · accent {cols.get('accent')} · {fonts.get('display')} / {fonts.get('ui')}"
          + ('' if a.no_record else f' · recorded in {HIST}') + '\n→ run sync.py so data.js picks up project.json')


ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
p = sub.add_parser('footage'); p.add_argument('--project', default='.')
p = sub.add_parser('history'); p.add_argument('-n', type=int, default=8)
p = sub.add_parser('deal'); p.add_argument('--project', default='.'); p.add_argument('--tags'); p.add_argument('--script', default='latin'); p.add_argument('--seed', type=int)
p = sub.add_parser('ramp'); p.add_argument('hex')
p = sub.add_parser('check'); p.add_argument('look'); p.add_argument('--project', default='.')
p = sub.add_parser('apply'); p.add_argument('look'); p.add_argument('--project', default='.'); p.add_argument('--no-record', action='store_true')
a = ap.parse_args()
{'footage': cmd_footage, 'history': cmd_history, 'deal': cmd_deal, 'ramp': cmd_ramp, 'check': cmd_check, 'apply': cmd_apply}[a.cmd](a)
