#!/usr/bin/env python3
"""Plan the cut from word timings: order the clips, trim dead heads/tails, tighten long pauses. Then remap words.

  python plan_cuts.py src/A.mp4 src/B.mp4 --transcripts transcripts --out edit [--fps 30]
        [--max-pause 0.35] [--keep-pause 0.16] [--head 0.08] [--tail 0.22]
  python plan_cuts.py --remap edit/cuts.json --transcripts transcripts --out edit    # after hand-editing cuts.json

Writes edit/cuts.json   {"fps", "segments": [{"clip", "start", "end"}], "joins": [output times of every cut]}
       edit/words.json  words in OUTPUT time (what captions and graphics are timed to)
       and prints a before/after summary.
Retakes, false starts and flubbed lines aren't detected automatically: read the transcript, then split or drop
segments in cuts.json by hand and run --remap.
"""
import argparse, json, os, re, subprocess
from pathlib import Path
from build import atomic_json, digest


def duration(path):
    e = subprocess.run(['ffmpeg', '-hide_banner', '-i', path], capture_output=True, text=True).stderr
    m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', e)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])


def words_for(clip, tdir):
    return json.load(open(os.path.join(tdir, os.path.splitext(os.path.basename(clip))[0] + '.words.json')))


def plan(clips, tdir, fps, max_pause, keep_pause, head, tail):
    fr = lambda t: round(t * fps) / fps
    segs = []
    for clip in clips:
        W, dur = words_for(clip, tdir), duration(clip)
        if not W: continue
        start = max(0.0, W[0]['s'] - head)
        for prev, w in zip(W, W[1:]):
            if w['s'] - prev['e'] > max_pause:
                segs.append({'clip': clip, 'start': fr(start), 'end': fr(prev['e'] + keep_pause / 2)})
                start = w['s'] - keep_pause / 2
        segs.append({'clip': clip, 'start': fr(start), 'end': fr(min(dur, W[-1]['e'] + tail))})
    return segs


def remap(segs, tdir, fps):
    out, words, joins, t = [], [], [], 0.0
    cache = {}
    for i, sg in enumerate(segs):
        W = cache.setdefault(sg['clip'], words_for(sg['clip'], tdir))
        for w in W:
            if sg['start'] - 0.02 <= w['s'] < sg['end']:
                words.append({'w': w['w'], 's': round(w['s'] - sg['start'] + t, 3), 'e': round(min(w['e'], sg['end']) - sg['start'] + t, 3)})
        t += sg['end'] - sg['start']
        if i < len(segs) - 1: joins.append(round(t, 4))
    return words, joins, round(t, 4)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('clips', nargs='*')
    ap.add_argument('--transcripts', default='transcripts')
    ap.add_argument('--out', default='edit')
    ap.add_argument('--fps', type=float, default=30)
    ap.add_argument('--max-pause', type=float, default=0.35)
    ap.add_argument('--keep-pause', type=float, default=0.16)
    ap.add_argument('--head', type=float, default=0.08)
    ap.add_argument('--tail', type=float, default=0.22)
    ap.add_argument('--remap', default=None)
    a = ap.parse_intermixed_args()
    os.makedirs(a.out, exist_ok=True)
    if a.remap:
        C = json.load(open(a.remap)); segs, fps = C['segments'], C.get('fps', a.fps)
    else:
        segs, fps = plan(a.clips, a.transcripts, a.fps, a.max_pause, a.keep_pause, a.head, a.tail), a.fps
    words, joins, total = remap(segs, a.transcripts, fps)
    json.dump({'fps': fps, 'segments': segs, 'joins': joins, 'duration': total}, open(os.path.join(a.out, 'cuts.json'), 'w'), indent=1)
    json.dump(words, open(os.path.join(a.out, 'words.json'), 'w'))
    atomic_json(Path(a.out) / '.words-timeline.json', {'segments': digest(segs)})
    src = sum(duration(c) for c in dict.fromkeys(s['clip'] for s in segs))
    print(f'{len(segs)} segments  {src:.2f} s of source → {total:.2f} s  (removed {src - total:.2f} s)')
    for s in segs: print(f"  {os.path.basename(s['clip'])}  {s['start']:7.3f} → {s['end']:7.3f}  ({s['end'] - s['start']:.2f} s)")
    print('joins at', joins)
