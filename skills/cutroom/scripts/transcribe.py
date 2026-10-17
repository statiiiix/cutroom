#!/usr/bin/env python3
"""Word-level transcription with faster-whisper large-v3-turbo (fast, accurate). One JSON per clip.

  python transcribe.py clip1.mp4 clip2.mp4 --out transcripts [--vocab "Claude, Claude Code, Codex"] [--lang en]
       [--model large-v3-turbo]

Writes transcripts/<clip>.words.json = [{"w": "Hello", "s": 0.12, "e": 0.40}, ...] and <clip>.txt.
The vocab list goes into Whisper's initial prompt: it fixes brand names, product names and people's names.
Runs on NVIDIA GPU (float16) when available, otherwise CPU int8. Long models on CPU: run in the background.
"""
import os, sys, json, subprocess, argparse, hashlib
from pathlib import Path
from build import atomic_json, digest
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')       # torch + ctranslate2 both ship OpenMP on macOS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('clips', nargs='+')
    ap.add_argument('--out', default='transcripts')
    ap.add_argument('--vocab', default='')
    ap.add_argument('--lang', default=None)
    ap.add_argument('--model', default='large-v3-turbo')
    ap.add_argument('--force', action='store_true', help='transcribe again even if source/options are unchanged')
    a = ap.parse_intermixed_args()
    model = None
    os.makedirs(a.out, exist_ok=True)
    receipt = Path(a.out) / '.cutroom-transcripts.json'
    records = json.loads(receipt.read_text()) if receipt.exists() else {}
    prompt = (a.vocab.strip() + '.') if a.vocab.strip() else None
    for clip in a.clips:
        base = os.path.splitext(os.path.basename(clip))[0]
        output = Path(a.out) / (base + '.words.json')
        text_output = Path(a.out) / (base + '.txt')
        sha = hashlib.sha256()
        with open(clip, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''): sha.update(chunk)
        key = digest([sha.hexdigest(), a.model, a.lang, a.vocab, Path(__file__).read_text()])
        previous = records.get(base, {})
        if not a.force and previous.get('input') == key and output.exists() and text_output.exists():
            # Text corrections are intentionally retained; only a changed source/options or --force re-infers.
            cached_text = ' '.join(w['w'] for w in json.loads(output.read_text()))
            text_output.write_text(cached_text + '\n')
            print(f'== {base} (reused transcript)\n' + cached_text)
            continue
        if model is None:
            import numpy as np
            from faster_whisper import WhisperModel
            try:
                import ctranslate2
                cuda = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                cuda = False
            model = WhisperModel(a.model, device='cuda' if cuda else 'cpu', compute_type='float16' if cuda else 'int8')
        # decode with ffmpeg ourselves (16 kHz mono float) so we never depend on PyAV's version
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', clip, '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                             capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, np.float32).copy()
        segs, info = model.transcribe(audio, word_timestamps=True, vad_filter=True, language=a.lang, initial_prompt=prompt,
                                      condition_on_previous_text=False)
        words = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3), 'p': round(w.probability, 3)}
                 for s in segs for w in (s.words or []) if w.word.strip()]
        json.dump(words, open(os.path.join(a.out, base + '.words.json'), 'w'))
        text = ' '.join(w['w'] for w in words)
        open(os.path.join(a.out, base + '.txt'), 'w').write(text + '\n')
        records[base] = {'input': key, 'source': str(Path(clip).resolve()), 'language': info.language}
        atomic_json(receipt, records)
        low = [w['w'] for w in words if w['p'] < 0.5]
        print(f'== {base}  ({info.language}, {len(words)} words)\n{text}')
        if low: print(f'   low-confidence words (check these): {", ".join(low)}')


if __name__ == '__main__':
    main()
