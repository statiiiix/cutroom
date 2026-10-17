#!/usr/bin/env python3
"""Rebuild only changed production stages after the editorial cut is approved.

  python build.py --project . --status
  python build.py --project . --to cut
  python build.py --project . --draft
  python build.py --project .                 # final, reusing unchanged picture/audio
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCHEMA = 1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False).encode()).hexdigest()


def read_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Build:
    def __init__(self, root, draft=False):
        self.root = Path(root).resolve()
        self.path = self.root / '.cutroom/build.json'
        self.state = read_json(self.path, {'schema': SCHEMA, 'stages': {}, 'files': {}})
        if self.state.get('schema') != SCHEMA:
            raise ValueError('Unsupported build state version; use a compatible Cutroom version.')
        self.draft = draft
        self.project = read_json(self.root / 'project.json')
        if not isinstance(self.project, dict):
            raise ValueError('project.json is missing; create an edit project first.')
        self.picture = 'renders/picture_draft.mp4' if draft else 'renders/picture.mp4'
        self.final = 'renders/draft.mp4' if draft else 'renders/final.mp4'

    def file(self, path):
        path = Path(path)
        path = path if path.is_absolute() else self.root / path
        if not path.is_file():
            return None
        stat = path.stat()
        key = str(path)
        stamp = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino]
        cache = self.state.setdefault('files', {}).get(key, {})
        if cache.get('stamp') != stamp:
            sha = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    sha.update(chunk)
            cache = {'stamp': stamp, 'sha256': sha.hexdigest()}
            self.state['files'][key] = cache
        return cache['sha256']

    def files(self, paths):
        return {str(p): self.file(p) for p in sorted(set(map(str, paths)))}

    def tree(self, folder, exclude=()):
        return self.files(p.relative_to(self.root) for p in (self.root / folder).rglob('*')
                          if p.is_file() and p.name not in exclude)

    def code(self, *names):
        return self.files(HERE / name for name in names)

    def enabled(self, stage):
        if stage == 'cut':
            return (self.root / 'edit/cuts.json').exists() or bool(self.project.get('clips'))
        if stage in ('sfx', 'mix'):
            return self.project.get('audio', True) is not False
        return True

    def key(self, stage):
        return stage + ('_draft' if self.draft and stage in ('picture', 'final') else '')

    def signature(self, stage):
        p = self.project
        if stage == 'cut':
            cuts = read_json(self.root / 'edit/cuts.json', {})
            clips = [s['clip'] for s in cuts.get('segments', [])]
            value = [cuts, self.files(clips), {k: p.get(k) for k in ('format', 'fps', 'voice', 'look')},
                     self.code('cut.py', 'probe.py')]
        elif stage == 'sync':
            value = [p, self.file('edit/words.json'), self.code('sync.py')]
        elif stage == 'sfx':
            value = [p.get('sfx', []), p.get('duration'), self.file('audio/cues.json'), self.code('sfx.py', 'sync.py')]
        elif stage == 'mix':
            value = [p.get('duration'), p.get('mix', {}),
                     self.files(['audio/voice.wav', 'audio/sfx.wav', 'audio/music.wav']), self.code('mix.py')]
        elif stage == 'picture':
            # data.js also contains audio-only settings. Fingerprint its visual data separately.
            visual = {k: v for k, v in p.items() if k not in ('mix', 'sfx', 'voice', 'profile', 'audio')}
            film = self.tree('film', exclude=('data.js',))
            source = '\n'.join(f.read_text(errors='replace') for f in (self.root / 'film').glob('*.js')
                               if f.name not in ('data.js', 'runtime.js', 'components.js', 'layouts.js'))
            sound_reactive = any(token in source for token in ('SFX', '.sfx', '["sfx"]', "['sfx']"))
            value = [visual, self.file('edit/words.json'), film, self.tree('assets'), self.draft,
                     p.get('sfx') if sound_reactive else None, self.code('render.mjs')]
        elif stage == 'final':
            value = [self.file(self.picture), p.get('audio', True),
                     self.file('audio/mix.wav') if p.get('audio', True) is not False else None,
                     self.code('render.mjs')]
        else:
            raise ValueError('Unknown stage: ' + stage)
        return digest([SCHEMA, stage, value])

    def outputs(self, stage):
        if stage == 'cut':
            foot = self.project.get('footage', {})
            count = foot.get('count', 0)
            if not isinstance(count, int) or count <= 0:
                return {}
            return self.files(['edit/cut.mov', 'edit/cut.mp4', 'audio/voice_raw.wav', 'audio/voice.wav'] +
                              [f'assets/foot/f{i:05d}.jpg' for i in range(count)])
        paths = {'sync': ['film/data.js', 'audio/cues.json'], 'sfx': ['audio/sfx.wav'],
                 'mix': ['audio/mix.wav'], 'picture': [self.picture], 'final': [self.final]}
        return self.files(paths[stage])

    def current(self, stage):
        record = self.state['stages'].get(self.key(stage), {})
        if record.get('signature') != self.signature(stage):
            return False, 'inputs changed or not built yet'
        outputs = self.outputs(stage)
        if not outputs or any(v is None for v in outputs.values()) or outputs != record.get('outputs'):
            return False, 'output missing or changed'
        return True, 'up to date'

    def command(self, stage):
        python = sys.executable
        node = os.environ.get('CUTROOM_NODE', 'node')
        common = ['--project', str(self.root)]
        if stage == 'picture':
            return [node, str(HERE / 'render.mjs'), *common, '--video-only', '--output', self.picture,
                    *(['--draft'] if self.draft else [])]
        if stage == 'final':
            return [node, str(HERE / 'render.mjs'), *common, '--mux', '--source', self.picture,
                    '--output', self.final, *(['--video-only'] if self.project.get('audio', True) is False else [])]
        return [python, str(HERE / (stage + '.py')), *common,
                *(['--look', self.project.get('look', 'auto')] if stage == 'cut' else [])]

    def retime_words(self):
        """Reorder source-timed words after a cut revision; retain confirmed text substitutions."""
        cuts_path = self.root / 'edit/cuts.json'
        cuts = read_json(cuts_path, {})
        segments = cuts.get('segments', [])
        duration, joins = 0, []
        for index, segment in enumerate(segments):
            length = segment['end'] - segment['start']
            if length <= 0:
                raise ValueError('Every cut segment must have a positive duration.')
            duration += length
            if index < len(segments) - 1:
                joins.append(round(duration, 4))
        if cuts.get('joins') != joins or cuts.get('duration') != round(duration, 4):
            cuts.update(joins=joins, duration=round(duration, 4))
            atomic_json(cuts_path, cuts)
        receipt_path = self.root / 'edit/.words-timeline.json'
        receipt = read_json(receipt_path, {})
        previous = self.state.get('word_timeline')
        if previous is None or digest(segments) == receipt.get('segments') or segments == previous:
            self.state['word_timeline'] = segments
            return
        source_words = {}
        for segment in [*previous, *segments]:
            clip = segment['clip']
            if clip not in source_words:
                words_path = self.root / 'transcripts' / (Path(clip).stem + '.words.json')
                if not words_path.exists():
                    raise ValueError(f'Cut changed: {words_path} is needed to remap captions. Supply source transcripts or run plan_cuts.py --remap first.')
                source_words[clip] = read_json(words_path)
        overrides = self.state.setdefault('word_overrides', {})
        current_words = read_json(self.root / 'edit/words.json', [])
        offset = 0
        for segment in previous:
            clip = segment['clip']
            length = segment['end'] - segment['start']
            for word in current_words:
                if offset - .02 <= word['s'] < offset + length:
                    source_time = word['s'] - offset + segment['start']
                    candidates = [(abs(original['s'] - source_time), index)
                                  for index, original in enumerate(source_words[clip])]
                    if candidates:
                        distance, index = min(candidates)
                        if distance < .025:
                            overrides[digest([clip, index, source_words[clip][index]['s']])] = word['w']
            offset += length
        words, offset = [], 0
        for segment in segments:
            clip = segment['clip']
            for index, word in enumerate(source_words[clip]):
                if segment['start'] - .02 <= word['s'] < segment['end']:
                    key = digest([clip, index, word['s']])
                    words.append({'w': overrides.get(key, word['w']),
                                  's': round(word['s'] - segment['start'] + offset, 3),
                                  'e': round(min(word['e'], segment['end']) - segment['start'] + offset, 3)})
            offset += segment['end'] - segment['start']
        atomic_json(self.root / 'edit/words.json', words)
        atomic_json(receipt_path, {'segments': digest(segments)})
        self.state['word_timeline'] = segments
        print(f'remapped {len(words)} words to the revised cut', flush=True)

    def run(self, target, status=False, force=False):
        result = []
        # sync changes affect audio and visual data independently; ownership of inputs
        # determines downstream work rather than blindly rebuilding all descendants.
        stages = ['cut', 'sync', 'sfx', 'mix', 'picture', 'final']
        dirty = set()
        dependencies = {'sync': ['cut'], 'sfx': ['cut'], 'mix': ['cut', 'sfx'],
                        'picture': ['cut'], 'final': ['picture', 'mix']}
        for stage in stages[:stages.index(target) + 1]:
            if not self.enabled(stage):
                result.append({'stage': stage, 'status': 'not needed'})
                continue
            current, reason = self.current(stage)
            upstream = any(dep in dirty for dep in dependencies.get(stage, []))
            if status:
                if upstream:
                    current, reason = False, 'upstream work pending'
                if not current:
                    dirty.add(stage)
                result.append({'stage': stage, 'status': 'current' if current else 'pending', 'reason': reason})
                continue
            if current and not force:
                print(f'skip {stage}: up to date', flush=True)
                result.append({'stage': stage, 'status': 'skipped'})
                continue
            if stage == 'cut' and not (self.root / 'edit/cuts.json').exists():
                raise ValueError('Plan and approve edit/cuts.json before building. The builder does not make editorial decisions.')
            print(f'build {stage}: {"forced" if force else reason}', flush=True)
            if stage == 'cut':
                self.retime_words()
            # Invalidate before starting: failure or interruption can never reuse an old receipt.
            self.state['stages'].pop(self.key(stage), None)
            atomic_json(self.path, self.state)
            subprocess.run(self.command(stage), cwd=self.root, check=True)
            self.project = read_json(self.root / 'project.json')
            outputs = self.outputs(stage)
            if not outputs or any(v is None for v in outputs.values()):
                raise ValueError(f'{stage} completed without its expected outputs')
            self.state['stages'][self.key(stage)] = {'signature': self.signature(stage), 'outputs': outputs}
            atomic_json(self.path, self.state)
            result.append({'stage': stage, 'status': 'built'})
        return result


@contextlib.contextmanager
def project_lock(root):
    import fcntl  # supported hosts: macOS, Linux, WSL
    folder = root / '.cutroom'
    folder.mkdir(exist_ok=True)
    with (folder / 'build.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another Cutroom build is running for this project.') from None
        yield


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', default='.')
    ap.add_argument('--status', action='store_true', help='show pending stages without changing files')
    ap.add_argument('--json', action='store_true', help='JSON status output (requires --status)')
    ap.add_argument('--draft', action='store_true', help='build/reuse the draft picture and draft.mp4')
    ap.add_argument('--to', choices=('cut', 'sync', 'sfx', 'mix', 'picture', 'final'), default='final')
    ap.add_argument('--force', action='store_true', help='rebuild all applicable stages through --to')
    a = ap.parse_args()
    if a.json and not a.status:
        ap.error('--json requires --status')
    root = Path(a.project).resolve()
    try:
        with (contextlib.nullcontext() if a.status else project_lock(root)):
            build = Build(root, a.draft)
            rows = build.run(a.to, a.status, a.force)
        if a.status:
            if a.json:
                print(json.dumps(rows, indent=2))
            else:
                for row in rows:
                    print(f"{row['stage']:8} {row['status']:10} {row.get('reason', '')}")
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        ap.exit(1, f'cutroom build: {exc}\n')


if __name__ == '__main__':
    main()
