#!/usr/bin/env python3
"""Scaffold an edit project from the user's style profile.

  python new_project.py <dir> --profile <style.md> [--format 9x16] clip1.mov clip2.mov ...

Creates <dir>/ with src/ (the clips), film/ (runtime + film.js from the template, colours and fonts from the
profile), assets/fonts (fetched), project.json, and empty edit/ audio/ renders/ review/ transcripts/.
Refuses a non-empty <dir>.
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from profile import settings
from styles import load_style

ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('clips', nargs='*')
ap.add_argument('--profile', required=True); ap.add_argument('--format', default=None)
ap.add_argument('--style', help='explicitly selected named saved style; does not change the profile')
ap.add_argument('--styles-dir', help='override CUTROOM_STYLES for this project')
a = ap.parse_intermixed_args()
if os.path.isdir(a.dir) and os.listdir(a.dir): sys.exit(f'REFUSING: {a.dir} exists and is not empty. Pick another name.')
S = settings(os.path.expanduser(a.profile))
saved = load_style(a.style, a.styles_dir) if a.style else None
if saved:
    for key, value in saved['settings'].items():
        if key in ('colors', 'fonts', 'captions', 'cut', 'sound', 'graphics', 'mix'):
            S[key] = {**S.get(key, {}), **value}
for d in ('src', 'film', 'assets/fonts', 'assets/brand', 'assets/foot', 'edit', 'audio', 'renders', 'review', 'transcripts'):
    os.makedirs(os.path.join(a.dir, d), exist_ok=True)
for c in a.clips: shutil.copy2(c, os.path.join(a.dir, 'src', os.path.basename(c)))
for f in ('runtime.js', 'layouts.js', 'index.html'): shutil.copy(os.path.join(SKILL, 'engine', f), os.path.join(a.dir, 'film', f))
shutil.copy(os.path.join(SKILL, 'engine', 'film.template.js'), os.path.join(a.dir, 'film', 'film.js'))

fonts = S.get('fonts', {}); written = {}
for role in ('display', 'ui'):
    fam = fonts.get(role) or fonts.get('display') or 'Inter'
    if role == 'ui' and fam == fonts.get('display') and 'display' in written:
        written['ui'] = written['display']; continue
    r = subprocess.run([sys.executable, os.path.join(HERE, 'get_font.py'), fam, os.path.join(a.dir, 'assets/fonts', role)], capture_output=True, text=True)
    if r.returncode: print(f'! font {fam!r} for {role}: {r.stderr.strip() or r.stdout.strip()} (falls back to Helvetica)')
    else: written[role] = os.path.basename(r.stdout.strip().splitlines()[-1])
html = open(os.path.join(a.dir, 'film/index.html')).read()
for role, fname in written.items():
    html = html.replace(f"url(../assets/fonts/{role}.woff2)", f"url(../assets/fonts/{fname})")
col = S.get('colors', {})
for k in ('text', 'ink', 'muted', 'accent', 'card', 'panel'):
    if k in col: html = __import__('re').sub(rf'--{k}: [^;]+;', f'--{k}: {col[k]};', html, 1)
open(os.path.join(a.dir, 'film/index.html'), 'w').write(html)

fmt = a.format or S.get('format', '9x16')
H = {'9x16': 1920, '16x9': 1080, '1x1': 1080, '4x5': 1350}[fmt]
cap = dict(S.get('captions', {})); pos = cap.pop('position', 0.745); cap['y'] = round(H * pos)
cap.pop('accentKeywords', None)
snd = S.get('sound', {})
P = {'name': os.path.basename(os.path.abspath(a.dir)), 'format': fmt, 'fps': S.get('fps', 30), 'duration': 10,
     'profile': os.path.abspath(os.path.expanduser(a.profile)), 'clips': [os.path.join('src', os.path.basename(c)) for c in a.clips],
     'captions': cap, 'voice': snd.get('voice', 'standard'), 'mix': {'voice': 0, 'sfx': -6, 'music': -20, 'duck': True, 'lufs': snd.get('lufs', -14), 'tp': -1},
     'sfx': [], 'cuts': []}
if saved:
    P['mix'].update(S.get('mix', {}))
    docs = Path(a.dir) / 'docs'
    docs.mkdir(exist_ok=True)
    shutil.copy2(saved['directory'] / 'direction.md', docs / 'style-direction.md')
    with (docs / 'style-settings.json').open('w') as stream:
        json.dump({key: S[key] for key in ('colors', 'fonts', 'captions', 'cut', 'sound', 'graphics', 'mix') if key in S}, stream, indent=2)
    refs = []
    for value in saved.get('references', []):
        source = (saved['directory'] / value).resolve()
        if not source.is_relative_to(saved['directory']) or not source.is_file():
            sys.exit(f'Saved style reference is missing or outside the style folder: {value}')
        (docs / 'style-references').mkdir(exist_ok=True)
        target = docs / 'style-references' / source.name
        shutil.copy2(source, target)
        refs.append(str(target.relative_to(Path(a.dir))))
    P['savedStyle'] = {'name': saved['name'], 'direction': 'docs/style-direction.md',
                       'settings': 'docs/style-settings.json', 'references': refs}
json.dump(P, open(os.path.join(a.dir, 'project.json'), 'w'), indent=1)
print(f'scaffolded {a.dir}  ({fmt}, fonts: {written or "fallback"}, {len(a.clips)} clips)')
