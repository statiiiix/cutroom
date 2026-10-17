#!/usr/bin/env python3
"""Probe clips without ffprobe: duration, size, fps, rotation, HDR, audio. Prints a table and writes JSON.

  python probe.py clip1.mov clip2.mp4 [--json out.json]

HDR = HLG (arib-std-b67) or PQ (smpte2084) transfer. iPhone "HDR Video" clips are HLG and need a tone-map (cut.py --look auto).
"""
import json, re, subprocess, sys


def probe(path):
    e = subprocess.run(['ffmpeg', '-hide_banner', '-i', path], capture_output=True, text=True).stderr
    out = {'path': path}
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', e)
    out['duration'] = round(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), 3) if m else None
    v = re.search(r'Stream #.*Video: (\w+).*?, (\w+)(\([^)]*\))?.*?, (\d{2,5})x(\d{2,5}).*?, ([\d.]+) (fps|tbr)', e)
    if v:
        out.update(codec=v[1], pix_fmt=v[2], width=int(v[4]), height=int(v[5]), fps=float(v[6]))
        tags = v[3] or ''
        out['color'] = tags.strip('()')
    rot = re.search(r'rotation of (-?[\d.]+) degrees', e) or re.search(r'rotate\s*:\s*(-?\d+)', e)
    out['rotation'] = float(rot[1]) if rot else 0.0
    if abs(out['rotation']) in (90.0, 270.0) and v:            # ffmpeg auto-rotates on decode: report display size
        out['width'], out['height'] = out['height'], out['width']
    col = out.get('color', '')
    out['hdr'] = 'hlg' if 'arib-std-b67' in col else 'pq' if 'smpte2084' in col else None
    out['ten_bit'] = bool(v and '10' in (v[2] or ''))
    out['audio'] = bool(re.search(r'Stream #.*Audio:', e))
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    res = [probe(p) for p in args if not p.endswith('.json')]
    for r in res:
        print(f"{r['path']}\n  {r.get('duration')} s  {r.get('width')}x{r.get('height')}  {r.get('fps')} fps  {r.get('codec')}  "
              f"{'HDR ' + r['hdr'].upper() if r['hdr'] else 'SDR'}  rot {r['rotation']:g}  {'audio' if r['audio'] else 'NO AUDIO'}")
    if '--json' in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
