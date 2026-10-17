#!/usr/bin/env python3
"""Mix voice + sfx (+ optional music, ducked under the voice) → audio/mix.wav at the target loudness.

  python mix.py [--project .]

Levels (dB) from project.json "mix": {"voice": 0, "sfx": -6, "music": -20, "duck": true, "lufs": -14, "tp": -1}
Any missing stem is skipped. Two-pass loudnorm (linear) to the target, then re-measured.
"""
import json, os, re, subprocess, sys

os.chdir(sys.argv[sys.argv.index('--project') + 1] if '--project' in sys.argv else '.')
P = json.load(open('project.json'))
M = {'voice': 0, 'sfx': -6, 'music': -20, 'duck': True, 'lufs': -14, 'tp': -1, **P.get('mix', {})}
D = P['duration']


def ff(args):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-y', *args], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-2000:])
    return r.stderr


stems = [(k, f'audio/{f}.wav') for k, f in (('voice', 'voice'), ('sfx', 'sfx'), ('music', 'music')) if os.path.exists(f'audio/{f}.wav')]
if not stems: sys.exit('no stems in audio/')
inputs, chains, labels = [], [], {}
for i, (k, f) in enumerate(stems):
    inputs += ['-i', f]
    chains.append(f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{D},volume={M[k]}dB[{k}]')
    labels[k] = f'[{k}]'
if 'music' in labels:
    chains[-1] = chains[-1].replace('[music]', f',afade=t=out:st={max(0, D - 0.6)}:d=0.6[music]')
    if M['duck'] and 'voice' in labels:
        chains += ['[voice]asplit[voice_o][voice_k]', '[music][voice_k]sidechaincompress=threshold=0.04:ratio=5:attack=20:release=300[music_d]']
        labels['voice'], labels['music'] = '[voice_o]', '[music_d]'
graph = ';'.join(chains) + ';' + ''.join(labels.values()) + f'amix=inputs={len(labels)}:normalize=0:duration=longest[m]'
ff([*inputs, '-filter_complex', graph, '-map', '[m]', '-c:a', 'pcm_f32le', 'audio/mix_raw.wav'])
st = ff(['-i', 'audio/mix_raw.wav', '-af', f"loudnorm=I={M['lufs']}:TP={M['tp'] - 0.5}:LRA=11:print_format=json", '-f', 'null', '-'])
j = json.loads(st[st.rindex('{'):st.rindex('}') + 1])
ln = (f"loudnorm=I={M['lufs']}:TP={M['tp'] - 0.5}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
      f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
ff(['-i', 'audio/mix_raw.wav', '-af', ln + ',aresample=48000', '-ar', '48000', '-c:a', 'pcm_s24le', 'audio/mix.wav'])
e = ff(['-nostats', '-i', 'audio/mix.wav', '-af', 'ebur128=peak=true', '-f', 'null', '-'])
s = e[e.rfind('Summary'):]
I = float(re.search(r'I:\s+(-?[\d.]+) LUFS', s)[1]); TP = float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', s)[1])
print(f"audio/mix.wav  stems: {', '.join(k for k, _ in stems)}  ·  {I:.1f} LUFS (target {M['lufs']})  ·  true peak {TP:.1f} dBTP")
if abs(I - M['lufs']) > 1 or TP > M['tp']:
    print('WARNING: off target (loudnorm fell back to dynamic mode or a stem clips). Lower the loudest stem and rerun.')
