#!/usr/bin/env python3
"""Synthesize sound effects from audio/cues.json → audio/sfx.wav (48 kHz stereo float). No samples needed.

  python sfx.py [--project .]

Types (cue time = the moment it should be heard):
  whoosh   air sweep that PEAKS on the cue (transitions, things flying in/out) · swish  short, lighter whoosh
  pop      something appears · click  cursor / button press · tick  typing, counters (quiet)
  thump    impact on a big word or number · ding  success / done · riser  2 s build peaking on the cue
If the user only likes some types, their style profile says so: use only those.
"""
import json, os, sys, struct
import numpy as np

os.chdir(sys.argv[sys.argv.index('--project') + 1] if '--project' in sys.argv else '.')
C = json.load(open('audio/cues.json'))
SR = C['sr']; N = int(SR * C['duration']) + SR
L = np.zeros(N, np.float32); R = np.zeros(N, np.float32)
TAU = 2 * np.pi


def noise(n, seed): return np.random.default_rng(seed).uniform(-1, 1, n).astype(np.float32)


def onepole_lp(x, fc):
    a = 1 - np.exp(-TAU * fc / SR); y = np.empty_like(x); z = 0.0
    for i in range(len(x)): z += a * (x[i] - z); y[i] = z
    return y


def hp(x, fc): return x - onepole_lp(x, fc)


def sweep_bp(x, fc_of_t, q=0.6):
    """state-variable band-pass with a moving centre frequency"""
    y = np.empty_like(x); lo = band = 0.0
    fcs = fc_of_t(np.arange(len(x)) / SR)
    for i in range(len(x)):
        f = 2 * np.sin(np.pi * min(fcs[i], SR / 6) / SR)
        lo += f * band; hi = x[i] - lo - q * band; band += f * hi; y[i] = band
    return y


def whoosh(seed, p=1.0, pre=0.32, post=0.16, amp=0.7):
    n = int((pre + post) * SR); t = np.arange(n) / SR
    y = sweep_bp(noise(n, seed), lambda tt: (300 + 6000 * np.minimum(1, tt / pre) ** 2) * p)
    env = np.where(t < pre, (t / pre) ** 2.2, np.exp(-(t - pre) * 22))
    return y * env * amp, pre, True


def swish(seed, p=1.0): return whoosh(seed, p * 1.3, pre=0.16, post=0.08, amp=0.55)


def pop(seed, p=1.0):
    n = int(0.1 * SR); t = np.arange(n) / SR
    f = (800 + 900 * (1 - np.exp(-t * 60))) * p
    y = np.sin(np.cumsum(TAU * f / SR)) * np.exp(-t * 42) * np.minimum(1, t / 0.002) * 0.8 + hp(noise(n, seed), 5000) * np.exp(-t * 3000) * 0.3
    return y, 0.0, False


def click(seed, p=1.0, g=1.0, length=0.05):
    n = int(length * SR); t = np.arange(n) / SR
    y = hp(hp(noise(n, seed), 3500), 3500) * np.exp(-t * 2600) * 0.9 + np.sin(TAU * 2300 * p * t) * np.exp(-t * 190) * 0.4 + np.sin(TAU * 520 * p * t) * np.exp(-t * 110) * 0.5
    return y * g, 0.0, False


def tick(seed, p=1.0): return click(seed, p * 1.25, 0.5, 0.03)


def thump(seed, p=1.0):
    n = int(0.55 * SR); t = np.arange(n) / SR
    f = (42 + 55 * np.exp(-t * 22)) * p
    y = np.tanh((np.sin(np.cumsum(TAU * f / SR)) * np.exp(-t * 7) + onepole_lp(noise(n, seed), 900) * np.exp(-t * 60) * 0.6) * 1.6)
    return y, 0.0, False


def ding(seed, p=1.0):
    n = int(0.7 * SR); t = np.arange(n) / SR
    y = sum(a * np.sin(TAU * 1320 * p * k * t) * np.exp(-t * d) for k, a, d in ((1, 0.6, 6), (2.01, 0.25, 9), (3.03, 0.12, 14)))
    return y * np.minimum(1, t / 0.003), 0.0, False


def riser(seed, p=1.0):
    pre = 2.0; n = int((pre + 0.03) * SR); t = np.arange(n) / SR
    y = sweep_bp(noise(n, seed), lambda tt: (300 + 7000 * np.minimum(1, tt / pre) ** 2.4) * p, 0.8)
    y = y * 0.8 + np.sin(np.cumsum(TAU * 220 * p * 2 ** (2 * np.minimum(1, t / pre)) / SR)) * 0.18
    return y * np.where(t < pre, (t / pre) ** 2.6, np.exp(-(t - pre) * 120)), pre, False


SYN = dict(whoosh=whoosh, swish=swish, pop=pop, click=click, tick=tick, thump=thump, ding=ding, riser=riser)
for c in C['cues']:
    if c['type'] not in SYN: sys.exit(f"unknown sfx type {c['type']!r}; have {', '.join(SYN)}")
    y, lead, stereo = SYN[c['type']](c['seed'], c.get('pitch', 1.0))
    s = int((c['t'] - lead) * SR); g = c['gain']
    pan = np.linspace(-0.6, 0.6, len(y)) if stereo else np.full(len(y), c.get('pan', 0.0))
    a, b = max(0, s), min(N, s + len(y)); y = y[a - s:b - s]; pan = pan[a - s:b - s]
    L[a:b] += y * g * np.sqrt(0.5 * (1 - pan)); R[a:b] += y * g * np.sqrt(0.5 * (1 + pan))

n = int(SR * C['duration']); data = np.stack([L[:n], R[:n]], 1).astype('<f4').tobytes()
hdr = b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 3, 2, SR, SR * 8, 8, 32) + b'data' + struct.pack('<I', len(data))
open('audio/sfx.wav', 'wb').write(hdr + data)
pk = max(np.abs(L).max(), np.abs(R).max(), 1e-9)
print(f"audio/sfx.wav  {len(C['cues'])} cues  peak {20 * np.log10(pk):.1f} dBFS")
