#!/usr/bin/env python3
"""Study a reference video's EDITING GRAMMAR (never its content): pacing, cuts, hook, caption look, framing.

  python reference.py <url-or-file> [--out refs] [--name mrbeast-short]

URL → downloads with yt-dlp (≤1080p) — ask the user first, and only for their own study. Then writes refs/<name>/:
  report.json   duration, cut times, cuts per minute, average / median shot length, loudness
  sheet.jpg     one frame every 0.5 s (motion graphics, layouts, B-roll, zooms)
  hook.jpg      the first 3 s at 6 fps (how the video grabs attention)
  captions.jpg  the lower 55 % of the frame every 0.5 s (caption font, size, colour, highlight, position)
LOOK at the images, then write what you learn into the user's style profile under "Reference notes".
"""
import argparse, json, os, re, statistics, subprocess, sys

ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('--out', default='refs'); ap.add_argument('--name', default=None)
a = ap.parse_args()
name = a.name or re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(a.src.split('?')[0]))[0].lower()).strip('-')[:40] or 'ref'
d = os.path.join(a.out, name); os.makedirs(d, exist_ok=True)
src = a.src
if re.match(r'https?://', src):
    tpl = os.path.join(d, 'video.%(ext)s')
    r = subprocess.run([sys.executable, '-m', 'yt_dlp', '-f', 'bv*[height<=1080]+ba/b[height<=1080]/b', '--merge-output-format', 'mp4', '-o', tpl, '--no-playlist', src])
    if r.returncode: sys.exit('download failed (yt-dlp). Ask the user for the file instead.')
    src = next(os.path.join(d, f) for f in os.listdir(d) if f.startswith('video.'))


def ff(args): return subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *args], capture_output=True, text=True).stderr


e = ff(['-i', src])
dur = sum(float(x) * m for x, m in zip(re.search(r'Duration: (\d+):(\d+):([\d.]+)', e).groups(), (3600, 60, 1)))
s = ff(['-i', src, '-vf', "select='gt(scene,0.32)',showinfo", '-af', 'ebur128', '-f', 'null', '-'])
cuts = [round(float(x), 2) for x in re.findall(r'pts_time:([\d.]+)', s)]
edges = [0.0] + cuts + [dur]
shots = [b - a2 for a2, b in zip(edges, edges[1:]) if b - a2 > 0.05]
I = re.search(r'I:\s+(-?[\d.]+) LUFS', s[s.rfind('Summary'):])
rep = {'source': a.src, 'duration': round(dur, 2), 'cuts': cuts, 'cuts_per_min': round(len(cuts) / dur * 60, 1),
       'avg_shot_s': round(statistics.mean(shots), 2), 'median_shot_s': round(statistics.median(shots), 2),
       'first_cut_s': cuts[0] if cuts else None, 'loudness_lufs': float(I[1]) if I else None}
json.dump(rep, open(os.path.join(d, 'report.json'), 'w'), indent=1)
n = int(dur / 0.5) + 1; cols = 10
ff(['-y', '-i', src, '-vf', f'fps=2,scale=216:-2,tile={cols}x{n // cols + 1}:padding=4', '-frames:v', '1', '-q:v', '4', os.path.join(d, 'sheet.jpg')])
ff(['-y', '-t', '3', '-i', src, '-vf', 'fps=6,scale=270:-2,tile=6x3:padding=4', '-frames:v', '1', '-q:v', '3', os.path.join(d, 'hook.jpg')])
ff(['-y', '-i', src, '-vf', f'fps=2,crop=iw:ih*0.55:0:ih*0.45,scale=270:-2,tile=8x{n // 8 + 1}:padding=4', '-frames:v', '1', '-q:v', '3', os.path.join(d, 'captions.jpg')])
print(json.dumps(rep, indent=1)); print(f'LOOK at {d}/hook.jpg, sheet.jpg, captions.jpg')
