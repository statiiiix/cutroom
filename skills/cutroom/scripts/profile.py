#!/usr/bin/env python3
"""Find, create or read the user's style profile.

  python profile.py find [--project .]         → prints the active profile path, or NONE
  python profile.py new <path> --name "Ahmad"  → writes a fresh profile from the template
  python profile.py settings <path>            → prints the JSON settings block

Lookup order (first hit wins): <project>/.cutroom/style.md → ./.cutroom/style.md → $CUTROOM_PROFILE →
~/.cutroom/style.md. People who edit for several brands keep one file per brand in ~/.cutroom/profiles/<brand>.md and
copy or link the right one to <project>/.cutroom/style.md (or set CUTROOM_PROFILE).
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find(project='.'):
    for p in (os.path.join(project, '.cutroom/style.md'), '.cutroom/style.md', os.environ.get('CUTROOM_PROFILE', ''), os.path.expanduser('~/.cutroom/style.md')):
        if p and os.path.exists(p): return os.path.abspath(p)
    return None


def settings(path):
    m = re.search(r'```json\s*(\{.*?\})\s*```', open(path).read(), re.S)
    if not m: sys.exit(f'{path}: no ```json settings block')
    return json.loads(m[1])


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'find'
    if cmd == 'find':
        print(find(sys.argv[sys.argv.index('--project') + 1] if '--project' in sys.argv else '.') or 'NONE')
    elif cmd == 'new':
        path = os.path.expanduser(sys.argv[2]); name = sys.argv[sys.argv.index('--name') + 1] if '--name' in sys.argv else 'me'
        if os.path.exists(path): sys.exit(f'{path} exists: edit it instead of overwriting')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        t = open(os.path.join(HERE, '../templates/style.md')).read().replace('{{NAME}}', name).replace('{{DATE}}', datetime.date.today().isoformat())
        open(path, 'w').write(t); print(path)
    elif cmd == 'settings':
        print(json.dumps(settings(os.path.expanduser(sys.argv[2])), indent=1))
