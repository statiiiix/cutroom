#!/usr/bin/env python3
"""Check a rendered video before showing it to anyone: loudness, black / frozen stretches, safe zones, phone-size sheet.

  python review.py renders/draft.mp4 [--project .] [--format 9x16]

Writes review/<name>_phone.jpg (1 frame per second at phone size) and review/<name>_safe.jpg (same, with the
platform UI zones shaded red: nothing important may sit there), and prints metrics. LOOK at both images.
"""
import json, os, re, subprocess, sys

args = [a for a in sys.argv[1:] if not a.startswith('--')]
video = args[0]
if '--project' in sys.argv: os.chdir(sys.argv[sys.argv.index('--project') + 1]); video = os.path.relpath(os.path.abspath(video))
fmt = sys.argv[sys.argv.index('--format') + 1] if '--format' in sys.argv else (json.load(open('project.json')).get('format', '9x16') if os.path.exists('project.json') else '9x16')
name = os.path.splitext(os.path.basename(video))[0]
os.makedirs('review', exist_ok=True)


def ff(a):
    return subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *a], capture_output=True, text=True).stderr


e = ff(['-i', video])
dur = sum(float(x) * m for x, m in zip(re.search(r'Duration: (\d+):(\d+):([\d.]+)', e).groups(), (3600, 60, 1)))
cols = 8 if fmt in ('9x16', '4x5') else 4
rows = int(dur // 1) // cols + 1
ff(['-y', '-i', video, '-vf', f'fps=1,scale=360:-2,tile={cols}x{rows}:padding=6:color=0x202020', '-frames:v', '1', '-q:v', '3', f'review/{name}_phone.jpg'])
# platform UI zones for 9:16 (Reels / TikTok / Shorts union): top 8 %, bottom 20 %, right 12 % below the middle
zones = {'9x16': "drawbox=y=0:w=iw:h=ih*0.08:color=red@0.35:t=fill,drawbox=y=ih*0.80:w=iw:h=ih*0.20:color=red@0.35:t=fill,"
                 "drawbox=x=iw*0.88:y=ih*0.45:w=iw*0.12:h=ih*0.35:color=red@0.35:t=fill,"}
ff(['-y', '-i', video, '-vf', f"fps=1,{zones.get(fmt, '')}scale=270:-2,tile={cols}x{rows}:padding=6:color=0x202020", '-frames:v', '1', '-q:v', '3', f'review/{name}_safe.jpg'])
s = ff(['-i', video, '-af', 'ebur128=peak=true', '-vf', 'blackdetect=d=0.15:pix_th=0.08,freezedetect=n=0.002:d=1.2', '-f', 'null', '-'])
summ = s[s.rfind('Summary'):]
I = re.search(r'I:\s+(-?[\d.]+) LUFS', summ); TP = re.search(r'Peak:\s+(-?[\d.]+) dBFS', summ)
black = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', s)
frozen = re.findall(r'freeze_start: ([\d.]+)', s)
m = {'duration': round(dur, 2), 'loudness_lufs': float(I[1]) if I else None, 'true_peak_dbtp': float(TP[1]) if TP else None,
     'black': [[float(a), float(b)] for a, b in black], 'frozen_from': [float(x) for x in frozen]}
json.dump(m, open(f'review/{name}_metrics.json', 'w'), indent=1)
print(json.dumps(m, indent=1))
print(f'LOOK at review/{name}_phone.jpg and review/{name}_safe.jpg')
if m['frozen_from']: print('NOTE: frozen picture for > 1.2 s — fine on a held graphic, a bug if the footage froze (decode/seek).')
