#!/usr/bin/env python3
"""Optional named styles from approved edits. Never changes the user's profile.

  python styles.py save "Clean explainer" --project . --notes docs/style-direction.md
  python styles.py list
  python styles.py show "Clean explainer"

Only invoke save after the user agrees to save that video as a style. Notes describe
creative direction; source footage, transcripts, graphics code and cue times are not saved.
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from build import atomic_json, read_json
from profile import settings as profile_settings

KEYS = ('colors', 'fonts', 'captions', 'cut', 'sound', 'graphics', 'mix')
HEIGHTS = {'9x16': 1920, '16x9': 1080, '1x1': 1080, '4x5': 1350}


def library(path=None):
    return Path(path or os.environ.get('CUTROOM_STYLES', '~/.cutroom/styles')).expanduser().resolve()


def slug(name):
    value = re.sub(r'[^\w-]+', '-', name.strip().lower(), flags=re.UNICODE).strip('-_')
    if not value or value in ('.', '..') or len(value) > 80:
        raise ValueError('Choose a short style name containing letters or numbers.')
    return value


def load_style(name, folder=None):
    candidate = Path(name).expanduser()
    # Names may contain punctuation or slashes; resolve their saved slug before
    # considering a relative path. Absolute paths remain explicit.
    if candidate.is_absolute():
        path = candidate
    else:
        named = library(folder) / slug(name)
        path = named if (named / 'style.json').is_file() else candidate if candidate.is_dir() or candidate.name == 'style.json' else named
    if path.is_dir():
        path /= 'style.json'
    data = read_json(path)
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('settings'), dict):
        raise ValueError(f'No supported saved style at {path}')
    result = copy.deepcopy(data)
    if set(result['settings']) - set(KEYS) or any(not isinstance(v, dict) for v in result['settings'].values()):
        raise ValueError('Saved styles contain visual, pacing and sound settings only.')
    result['directory'] = path.parent.resolve()
    for role, value in result['settings'].get('fonts', {}).items():
        if not isinstance(value, str):
            raise ValueError('Saved font names must be strings.')
        if value.startswith('fonts/'):
            font = (path.parent / value).resolve()
            if not font.is_relative_to(path.parent.resolve()) or not font.is_file():
                raise ValueError(f'Saved font is missing: {value}')
            result['settings']['fonts'][role] = str(font)
    if not (path.parent / 'direction.md').is_file():
        raise ValueError('Saved style has no creative direction notes.')
    return result


def save(name, project, notes, folder=None, stills=(), overrides=None):
    project = Path(project).expanduser().resolve()
    p = read_json(project / 'project.json')
    if not isinstance(p, dict):
        raise ValueError('Choose a Cutroom project with project.json.')
    notes_path = Path(notes).expanduser()
    if not notes_path.is_absolute():
        notes_path = project / notes_path
    direction = notes_path.read_text().strip()
    if len(direction) < 20:
        raise ValueError('Describe the approved visual language, motion, pacing and sound in the notes.')
    destination = library(folder) / slug(name)
    if destination.exists():
        raise ValueError(f'{destination} already exists; choose a different name.')
    profile = Path(p['profile']).expanduser() if p.get('profile') else None
    if profile and not profile.is_absolute():
        profile = project / profile
    s = profile_settings(profile) if profile and profile.is_file() else {}
    s = {key: copy.deepcopy(s[key]) for key in KEYS if key in s}
    # A variation starts with this project's selected direction, not the base profile.
    selected = p.get('savedStyle', {}).get('settings')
    if selected:
        selected_path = (project / selected).resolve()
        if not selected_path.is_relative_to(project):
            raise ValueError('Project style settings must stay inside the project.')
        effective = read_json(selected_path)
        if not isinstance(effective, dict) or set(effective) - set(KEYS) or any(not isinstance(v, dict) for v in effective.values()):
            raise ValueError('Project style settings must contain supported setting objects.')
        for key, value in effective.items():
            s.setdefault(key, {}).update(copy.deepcopy(value))
    # Capture declared colors from the completed film, including per-video changes.
    html = project / 'film/index.html'
    if html.exists():
        css = html.read_text()
        for key in ('text', 'ink', 'muted', 'accent', 'card', 'panel'):
            matches = re.findall(r'--' + key + r'\s*:\s*([^;{}]+);', css)
            if matches:
                s.setdefault('colors', {})[key] = matches[-1].strip()
    if p.get('captions'):
        captions = copy.deepcopy(p['captions'])
        if 'y' in captions:
            captions['position'] = captions.pop('y') / HEIGHTS[p.get('format', '9x16')]
        for key in ('keywords', 'hidden', 'times'):
            captions.pop(key, None)
        s['captions'] = captions
    sound = s.setdefault('sound', {})
    if p.get('voice'):
        sound['voice'] = p['voice']
    sound['music'] = 'bed' if (project / 'audio/music.wav').exists() else 'none'
    if 'sfx' in p:
        sound['sfx'] = sorted({cue['type'] for cue in p['sfx']})
    if p.get('mix'):
        s['mix'] = copy.deepcopy(p['mix'])
    # Explicit settings let the editor describe rendered decisions not expressible in CSS variables.
    supplied = {}
    if overrides:
        supplied_path = Path(overrides).expanduser()
        supplied = read_json(supplied_path if supplied_path.is_absolute() else project / supplied_path)
        if not isinstance(supplied, dict) or set(supplied) - set(KEYS):
            raise ValueError('Style overrides support only: ' + ', '.join(KEYS))
        for key, value in supplied.items():
            if not isinstance(value, dict):
                raise ValueError(f'{key} style settings must be an object.')
            s.setdefault(key, {}).update(value)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.saving-style-', dir=parent))
    try:
        # Preserve the actual installed font files when available; never copy the film or footage.
        font_spec = dict(s.get('fonts', {}))
        for role in ('display', 'ui'):
            explicitly_set = role in supplied.get('fonts', {})
            candidates = [] if explicitly_set else sorted((project / 'assets/fonts').glob(role + '.*'))
            if not candidates and font_spec.get(role):
                value = Path(font_spec[role]).expanduser()
                if value.is_file():
                    candidates = [value]
                elif not explicitly_set and role == 'ui' and font_spec.get('ui') == font_spec.get('display'):
                    candidates = sorted((project / 'assets/fonts').glob('display.*'))
            if candidates:
                source = candidates[0]
                if source.suffix.lower() not in ('.woff2', '.woff', '.ttf', '.otf'):
                    raise ValueError(f'Unsupported font file: {source}')
                (stage / 'fonts').mkdir(exist_ok=True)
                rel = 'fonts/' + role + source.suffix.lower()
                shutil.copyfile(source, stage / rel)
                s.setdefault('fonts', {})[role] = rel
        references = []
        for index, value in enumerate(stills):
            source = Path(value).expanduser()
            if not source.is_absolute():
                source = project / source
            if source.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp') or not source.is_file():
                raise ValueError(f'Choose an existing rendered still: {source}')
            (stage / 'references').mkdir(exist_ok=True)
            rel = f'references/{index + 1:02d}{source.suffix.lower()}'
            shutil.copyfile(source, stage / rel)
            references.append(rel)
        atomic_json(stage / 'style.json', {'schema': 1, 'name': name.strip(),
                    'created': datetime.date.today().isoformat(), 'settings': s,
                    'reference_format': p.get('format'), 'references': references})
        (stage / 'direction.md').write_text(direction + '\n')
        # No replacement mode: two styles cannot silently overwrite one another.
        stage.rename(destination)
        print(f'Saved style {name!r}: {destination}')
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--library', help='style library location; default CUTROOM_STYLES or ~/.cutroom/styles')
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    show = sub.add_parser('show'); show.add_argument('name')
    create = sub.add_parser('save'); create.add_argument('name')
    create.add_argument('--project', default='.')
    create.add_argument('--notes', required=True)
    create.add_argument('--still', action='append', default=[], help='optional approved reference frame; repeat as needed')
    create.add_argument('--settings', help='optional JSON overrides for rendered style settings')
    a = ap.parse_args()
    try:
        if a.command == 'save':
            save(a.name, a.project, a.notes, a.library, a.still, a.settings)
        elif a.command == 'show':
            style = load_style(a.name, a.library)
            print(json.dumps({k: v for k, v in style.items() if k != 'directory'}, indent=2, ensure_ascii=False))
            print('\n' + (style['directory'] / 'direction.md').read_text())
        else:
            root = library(a.library)
            for path in sorted(root.glob('*/style.json')) if root.exists() else []:
                style = load_style(str(path))
                print(f"{path.parent.name}\t{style['name']}")
    except (ValueError, KeyError, OSError) as exc:
        ap.exit(1, f'cutroom styles: {exc}\n')


if __name__ == '__main__':
    main()
