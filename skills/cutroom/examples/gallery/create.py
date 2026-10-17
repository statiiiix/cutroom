#!/usr/bin/env python3
"""Create a local, offline component gallery project. No footage or profile required.

python3 skills/cutroom/examples/gallery/create.py /tmp/cutroom-gallery --format all
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
FORMATS = ('9x16', '16x9', '1x1', '4x5')


def create(destination, fmt):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f'REFUSING: {destination} is not empty')
    for directory in ('film', 'audio', 'assets', 'renders', 'review', 'edit'):
        (destination / directory).mkdir(parents=True, exist_ok=True)
    for name in ('runtime.js', 'layouts.js', 'components.js', 'index.html'):
        shutil.copy2(SKILL / 'engine' / name, destination / 'film' / name)
    shutil.copy2(HERE / 'film.js', destination / 'film' / 'film.js')
    html_path = destination / 'film' / 'index.html'
    html = re.sub(r'\s*@font-face\s*\{[^}]+\}', '', html_path.read_text())
    html = html.replace("'Display', 'Helvetica Neue'", "'Helvetica Neue'").replace("'UI', 'Helvetica Neue'", "'Helvetica Neue'")
    for token, value in {'text': '#f4f7fa', 'ink': '#182735', 'muted': '#5b7083', 'accent': '#2856e8', 'card': '#ffffff', 'panel': '#182735', 'line': '#cad5de'}.items():
        html = re.sub(rf'--{token}: [^;]+;', f'--{token}: {value};', html, count=1)
    html_path.write_text(html)
    project = {'name': f'cutroom-gallery-{fmt}', 'format': fmt, 'fps': 30, 'duration': 24,
               'clips': [], 'cuts': [], 'sfx': [], 'audio': False, 'captions': {'mode': 'off'}}
    (destination / 'project.json').write_text(json.dumps(project, indent=2) + '\n')
    subprocess.run([sys.executable, str(SKILL / 'scripts' / 'sync.py'), '--project', str(destination)], check=True)
    print(f'created {destination} ({fmt})')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--format', choices=(*FORMATS, 'all'), default='9x16')
    args = parser.parse_args()
    formats = FORMATS if args.format == 'all' else (args.format,)
    destinations = [(args.destination / fmt if args.format == 'all' else args.destination).resolve() for fmt in formats]
    # Validate every target before writing any of them.
    for destination in destinations:
        if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
            parser.error(f'REFUSING: {destination} exists and is not an empty directory')
    for destination, fmt in zip(destinations, formats):
        create(destination, fmt)


if __name__ == '__main__':
    main()
