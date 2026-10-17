#!/usr/bin/env python3
"""Apply edit/cuts.json: one continuous take as a JPG frame sequence (for the film) plus raw and cleaned voice.

  python cut.py [--project .] [--look auto|none|hdr] [--voice off|light|standard|strong] [--look-check]

Reads project.json (format, fps) and edit/cuts.json. Writes:
  assets/foot/f00000.jpg …   the footage the film draws under the graphics (cover-cropped to the format)
  edit/cut.mp4               a plain preview of the cut (with original audio)
  audio/voice_raw.wav        the cut's audio, untouched
  audio/voice.wav            cleaned voice (HPF, denoise, de-mud, presence, de-ess, gentle compression)
  and updates project.json: duration, footage {fps, count}, cuts (join times).
--look-check writes review/look_check.jpg (source vs graded) and stops: show it before building on an HDR grade.

Look: SDR clips are left untouched. HDR (iPhone HLG / PQ) is tone-mapped with hable at 203 nits plus gamma 0.92,
which keeps skin natural (mobius looks hazy; a plain zscale without tone-map turns yellow and blown out).
"""
import argparse, json, os, subprocess, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from probe import probe

SIZES = {'9x16': (1080, 1920), '16x9': (1920, 1080), '1x1': (1080, 1080), '4x5': (1080, 1350)}
HDR = 'zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,eq=gamma=0.92'
VOICE = {
    'off': None,
    'light': 'highpass=f=70,afftdn=nf=-32,acompressor=threshold=-18dB:ratio=2:attack=10:release=150:makeup=1',
    'standard': 'highpass=f=80,afftdn=nf=-28:tn=1,equalizer=f=250:t=q:w=1.2:g=-2.5,equalizer=f=3500:t=q:w=1.0:g=2.5,'
                'equalizer=f=11000:t=h:w=0.7:g=1.5,deesser=i=0.35,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2',
    'strong': 'highpass=f=90,afftdn=nf=-24:tn=1,equalizer=f=250:t=q:w=1.2:g=-3.5,equalizer=f=3500:t=q:w=1.0:g=3,'
              'equalizer=f=11000:t=h:w=0.7:g=2,deesser=i=0.5,acompressor=threshold=-22dB:ratio=4:attack=6:release=100:makeup=3',
}


def ff(args):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'error', '-y', *args], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-3000:])


def has_filter(name):
    return f' {name} ' in subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default='.')
    ap.add_argument('--look', default='auto')
    ap.add_argument('--voice', default=None)
    ap.add_argument('--look-check', action='store_true')
    a = ap.parse_intermixed_args()
    os.chdir(a.project)
    P = json.load(open('project.json'))
    C = json.load(open('edit/cuts.json'))
    W, H = SIZES[P.get('format', '9x16')]
    fps = C.get('fps', P.get('fps', 30))
    voice = a.voice or P.get('voice', 'standard')
    clips = list(dict.fromkeys(s['clip'] for s in C['segments']))
    info = {c: probe(c) for c in clips}
    hdr = lambda c: (a.look == 'hdr') or (a.look == 'auto' and info[c]['hdr'])
    if any(hdr(c) for c in clips) and not has_filter('zscale'):
        sys.exit('HDR footage needs ffmpeg built with libzimg (zscale). macOS: brew reinstall ffmpeg.')
    fit = f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1'

    if a.look_check:
        c = next((c for c in clips if hdr(c)), clips[0]); t = C['segments'][0]['start'] + 1
        os.makedirs('review', exist_ok=True)
        graded = f'{HDR},' if hdr(c) else ''
        ff(['-ss', str(t), '-i', c, '-filter_complex', f'[0:v]split[a][b];[a]{fit},scale=540:-2[x];[b]{graded}{fit},scale=540:-2[y];[x][y]hstack',
            '-frames:v', '1', 'review/look_check.jpg'])
        print('wrote review/look_check.jpg (left: source as decoded, right: graded)'); return

    idx = {c: i for i, c in enumerate(clips)}
    v, au, n = [], [], len(C['segments'])
    for k, s in enumerate(C['segments']):
        i, d = idx[s['clip']], s['end'] - s['start']
        look = f'{HDR},' if hdr(s['clip']) else 'format=yuv420p,'
        v.append(f"[{i}:v]trim=start={s['start']}:end={s['end']},setpts=PTS-STARTPTS,{look}{fit},fps={fps}[v{k}]")
        au.append(f"[{i}:a]atrim=start={s['start']}:end={s['end']},asetpts=PTS-STARTPTS,aresample=48000,"
                  f"afade=t=in:d=0.012,afade=t=out:st={max(0, d - 0.015):.4f}:d=0.015[a{k}]")
    graph = ';'.join(v + au) + ';' + ''.join(f'[v{k}]' for k in range(n)) + f'concat=n={n}:v=1:a=0[v];' + \
        ''.join(f'[a{k}]' for k in range(n)) + f'concat=n={n}:v=0:a=1[a]'
    inputs = sum([['-i', c] for c in clips], [])
    os.makedirs('edit', exist_ok=True); os.makedirs('audio', exist_ok=True); os.makedirs('assets/foot', exist_ok=True)
    ff([*inputs, '-filter_complex', graph, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '14', '-preset', 'fast',
        '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-c:a', 'pcm_s16le', 'edit/cut.mov'])
    for f in glob.glob('assets/foot/*.jpg'): os.remove(f)
    ff(['-i', 'edit/cut.mov', '-q:v', '2', '-start_number', '0', 'assets/foot/f%05d.jpg'])
    ff(['-i', 'edit/cut.mov', '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-c:a', 'aac', '-movflags', '+faststart', 'edit/cut.mp4'])
    ff(['-i', 'edit/cut.mov', '-vn', '-ac', '1', '-ar', '48000', 'audio/voice_raw.wav'])
    chain = VOICE[voice]
    if chain and not has_filter('deesser'): chain = ','.join(p for p in chain.split(',') if not p.startswith('deesser'))
    ff(['-i', 'audio/voice_raw.wav', *(['-af', chain] if chain else []), '-ar', '48000', 'audio/voice.wav'])
    count = len(glob.glob('assets/foot/*.jpg'))
    P.update(duration=round(count / fps, 4), fps=P.get('fps', fps), footage={'fps': fps, 'count': count}, cuts=C['joins'])
    json.dump(P, open('project.json', 'w'), indent=1)
    print(f"cut: {count} frames @ {fps} fps = {count / fps:.2f} s · look {'HDR tone-map' if any(hdr(c) for c in clips) else 'untouched (SDR)'} · voice {voice}")


if __name__ == '__main__':
    main()
