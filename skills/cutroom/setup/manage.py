#!/usr/bin/env python3
"""Self-contained Cutroom lifecycle manager. Only Python's standard library is needed.

Managed skill files are inventoried; unknown files, profiles, projects and shared
runtimes survive target removal. No shell startup files or global agent settings
are edited. Updates resolve official GitHub commits or verify explicit custom packages;
archives are extracted without links.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shlex
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile

SETUP = Path(__file__).resolve().parent
SKILL = SETUP.parent
VERSION = json.loads((SETUP / 'version.json').read_text())
MARKER = '.cutroom-install.json'
STATE = '.cutroom-runtime.json'
PROTECTED = {'projects', 'profiles', 'styles', '.cutroom', 'style.md', 'memory'}
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024


class SetupError(Exception):
    pass


def absolute(value):
    return Path(value).expanduser().absolute()


def runtime_home():
    home = absolute(os.environ.get('CUTROOM_HOME', str(Path.home() / '.cutroom'))).resolve()
    if home in {Path('/'), Path.home().resolve()}:
        raise SetupError('CUTROOM_HOME must be a dedicated directory, not / or your home directory.')
    return home


def env_for(home):
    env = os.environ.copy()
    env.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(home / 'browsers'))
    env.setdefault('PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT', '120000')
    env.setdefault('PIP_CACHE_DIR', str(home / 'cache/pip'))
    env.setdefault('npm_config_cache', str(home / 'cache/npm'))
    return env


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise SetupError(f'Cannot read {path}: {exc}') from exc


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(data, indent=2) + '\n')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def relative_file(name):
    path = PurePosixPath(name)
    if not path.parts or '\\' in name or path.is_absolute() or '..' in path.parts:
        raise SetupError(f'Unsafe package or inventory path: {name!r}')
    if path.parts[0] in PROTECTED or path.parts[0].startswith('.'):
        raise SetupError(f'Reserved user-data path in package or inventory: {name}')
    return path


def pins(source=SKILL):
    result = {}
    for line in (source / 'setup/requirements.txt').read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)', line)
        if not match:
            raise SetupError(f'Dependency must be exactly pinned: {line}')
        result[match[1]] = match[2]
    return result


def source_files(source):
    required = ['SKILL.md', 'setup/manage.py', 'setup/install.sh', 'setup/version.json',
                'setup/requirements.txt', 'setup/package.json', 'setup/package-lock.json',
                'scripts/manage.py', 'scripts/cutroom', 'scripts/doctor.sh']
    for name in required:
        if not (source / name).is_file():
            raise SetupError(f'Package is incomplete: {name} is missing.')
    if not re.search(r'^name:\s*cutroom\s*$', (source / 'SKILL.md').read_text(), re.M):
        raise SetupError('Package does not contain the Cutroom skill.')
    version = read_json(source / 'setup/version.json')
    package = read_json(source / 'setup/package.json')
    lock = read_json(source / 'setup/package-lock.json')
    if version.get('name') != 'cutroom' or version.get('setup_schema') != 1:
        raise SetupError('Unsupported Cutroom package metadata.')
    if package.get('version') != version.get('version') or lock.get('version') != version.get('version'):
        raise SetupError('Package, lockfile and version metadata do not agree.')
    if lock.get('packages', {}).get('', {}).get('dependencies') != package.get('dependencies'):
        raise SetupError('The npm lockfile does not match package.json.')
    for name, value in package.get('dependencies', {}).items():
        if not re.fullmatch(r'\d+\.\d+\.\d+', value):
            raise SetupError(f'Node dependency is not pinned: {name}={value}')
    pins(source)
    files = {}
    installed = read_json(source / MARKER, {})
    owned = installed.get('files') if installed.get('name') == 'cutroom' else None
    paths = [source / str(relative_file(name)) for name in owned] if isinstance(owned, dict) else source.rglob('*')
    for path in sorted(paths):
        rel = path.relative_to(source)
        if any(p in {'__pycache__', '.git', 'node_modules'} for p in rel.parts) or path.suffix == '.pyc' or path.name in {MARKER, '.DS_Store'}:
            continue
        if path.is_symlink():
            raise SetupError(f'Package symlinks are not supported: {rel}')
        if path.is_file():
            relative_file(rel.as_posix())
            files[rel.as_posix()] = digest(path)
    return files


def run(command, *, home=None, cwd=None, dry=False):
    print('  $ ' + shlex.join(map(str, command)), flush=True)
    if dry:
        return
    try:
        subprocess.run(list(map(str, command)), cwd=cwd, env=env_for(home) if home else None, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SetupError(f'Command failed: {shlex.join(map(str, command))}: {exc}') from exc


def capture(command, *, home=None, cwd=None, timeout=30):
    try:
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True,
                                cwd=cwd, env=env_for(home) if home else None, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, '', str(exc)


def system_checks():
    checks = []
    def add(name, ok, detail, fix=''):
        checks.append({'name': name, 'status': 'ok' if ok else 'fail', 'detail': detail, 'fix': fix if not ok else ''})
    system, arch = platform.system(), platform.machine()
    add('platform', system in {'Darwin', 'Linux'} and arch in {'arm64', 'aarch64', 'x86_64', 'AMD64'},
        f'{system} {platform.release()} / {arch}', 'Use macOS or Linux on x86_64/arm64.')
    if system == 'Darwin':
        major = int((platform.mac_ver()[0] or '0').split('.')[0])
        add('macOS', major >= 13, platform.mac_ver()[0], 'Use macOS 13 or later for the pinned Chromium build.')
    current = sys.version_info[:2]
    add('bootstrap Python', tuple(VERSION['python_min']) <= current < tuple(VERSION['python_max_exclusive']),
        sys.version.split()[0], 'Run setup with Python 3.10–3.13 (python3 -m venv must be available).')
    ok, out, err = capture(['node', '--version'])
    match = re.match(r'v(\d+)\.', out)
    node_ok = ok and match and VERSION['node_min'] <= int(match[1]) < VERSION['node_max_exclusive']
    add('Node.js', bool(node_ok), out or err or 'missing', 'Install Node.js 20, 22 or 24 with npm; then rerun repair.')
    ok, out, err = capture(['npm', '--version'])
    add('npm', ok, out or err or 'missing', 'Install npm with the supported Node.js distribution.')
    ok, out, err = capture(['ffmpeg', '-version'])
    first = (out or err).splitlines()[0] if out or err else 'missing'
    match = re.search(r'ffmpeg version (?:n)?(\d+)', out)
    add('FFmpeg', bool(ok and match and int(match[1]) >= VERSION['ffmpeg_min']), first,
        'Install FFmpeg 6+ with libx264/AAC: brew install ffmpeg; or sudo apt install ffmpeg.')
    if ok:
        filters_ok, filters, _ = capture(['ffmpeg', '-hide_banner', '-filters'])
        required = ['scale', 'crop', 'fps', 'loudnorm', 'amix', 'concat', 'aresample']
        missing = [name for name in required if not re.search(r'\s' + name + r'\s', filters)]
        add('FFmpeg editing filters', filters_ok and not missing, 'available' if not missing else ', '.join(missing), 'Install a full FFmpeg build.')
        encoders_ok, encoders, _ = capture(['ffmpeg', '-hide_banner', '-encoders'])
        missing = [name for name in ['libx264', 'aac'] if not re.search(r'\s' + name + r'\s', encoders)]
        add('FFmpeg H.264/AAC', encoders_ok and not missing, 'available' if not missing else ', '.join(missing), 'Install FFmpeg with libx264 and AAC encoders.')
        checks.append({'name': 'HDR tone mapping', 'status': 'ok' if re.search(r'\szscale\s', filters) else 'warn',
                       'detail': 'zscale available' if re.search(r'\szscale\s', filters) else 'zscale missing; SDR editing works, HDR footage needs libzimg.', 'fix': ''})
    return checks


def machine_info(home):
    memory = None
    try:
        memory = round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 1024 ** 3, 1)
    except (ValueError, OSError, AttributeError):
        if platform.system() == 'Darwin':
            ok, out, _ = capture(['sysctl', '-n', 'hw.memsize'])
            if ok:
                memory = round(int(out) / 1024 ** 3, 1)
    existing = home
    while not existing.exists():
        existing = existing.parent
    return {'cpu_cores': os.cpu_count(), 'memory_gib': memory,
            'free_disk_gib': round(shutil.disk_usage(existing).free / 1024 ** 3, 1),
            'architecture': platform.machine(), 'system': platform.system()}


def doctor(home, as_json=False, source=SKILL):
    checks = system_checks()
    required_files = ['scripts/cut.py', 'scripts/mix.py', 'scripts/sfx.py', 'scripts/transcribe.py',
                      'scripts/render.mjs', 'scripts/build.py', 'scripts/new_project.py',
                      'engine/runtime.js', 'engine/layouts.js', 'engine/index.html', 'scripts/styles.py']
    missing_files = [name for name in required_files if not (source / name).is_file()]
    checks.append({'name': 'Skill editing files', 'status': 'fail' if missing_files else 'ok',
                   'detail': ', '.join(missing_files) if missing_files else 'available',
                   'fix': 'Run repair --no-model to restore managed files from the recovery cache, or update.' if missing_files else ''})
    py = home / 'venv/bin/python'
    expected = pins(source)
    probe = '''import importlib.metadata as m, json, sys
import faster_whisper, numpy, yt_dlp, certifi, av, ctranslate2
try: devices = ctranslate2.get_cuda_device_count()
except Exception: devices = 0
print(json.dumps({'versions': {name: m.version(name) for name in sys.argv[1:]},
'python': list(sys.version_info[:2]), 'cpu_compute_types': sorted(ctranslate2.get_supported_compute_types('cpu')), 'cuda_devices': devices}))'''
    if not as_json:
        print('Checking native Python packages (first import can take a few minutes on macOS)…', flush=True)
    ok, out, err = capture([py, '-c', probe, *expected], home=home, timeout=300)
    native = {}
    if ok:
        try:
            native = json.loads(out)
            mismatch = [f'{name}: {native["versions"].get(name)} (expected {value})' for name, value in expected.items() if native['versions'].get(name) != value]
            native_python = tuple(native['python'])
            if not tuple(VERSION['python_min']) <= native_python < tuple(VERSION['python_max_exclusive']):
                mismatch.append('venv Python must be 3.10–3.13')
            if 'int8' not in native.get('cpu_compute_types', []):
                mismatch.append('CTranslate2 CPU int8 is unavailable')
            ok = not mismatch
            detail = '; '.join(mismatch) if mismatch else ', '.join(f'{k} {v}' for k, v in native['versions'].items())
        except (ValueError, KeyError, TypeError) as exc:
            ok, detail = False, str(exc)
    else:
        detail = err[-1400:] or 'private Python environment is missing'
    checks.append({'name': 'Python packages and CPU transcription', 'status': 'ok' if ok else 'fail', 'detail': detail,
                   'fix': f'Run {SKILL / "scripts/cutroom"} repair --no-model' if not ok else ''})
    if py.is_file():
        ok, out, err = capture([py, '-m', 'pip', 'check'], home=home, timeout=60)
        checks.append({'name': 'Python dependency consistency', 'status': 'ok' if ok else 'fail', 'detail': out or err,
                       'fix': 'Run repair --no-model to reconcile dependencies.' if not ok else ''})
    node_dir = home / 'node'
    browser = '''const playwright = process.argv[2]; const { chromium } = require(playwright);
(async () => { const p = require(playwright + '/package.json');
if(p.version !== process.argv[1]) throw new Error(`Playwright ${p.version}; expected ${process.argv[1]}`);
const b = await chromium.launch({headless:true});
try { const page = await b.newPage(); await page.setContent('<canvas width="8" height="8"></canvas>');
if (!await page.evaluate(() => !!document.querySelector('canvas').getContext('2d'))) throw new Error('Canvas 2D unavailable');
console.log(JSON.stringify({playwright:p.version,chromium:b.version(),canvas2d:true})); }
finally { await b.close(); }
})().catch(e=>{console.error(e.message);process.exit(1)});'''
    expected_pw = read_json(source / 'setup/package.json')['dependencies']['playwright']
    ok, out, err = capture(['node', '-e', browser, expected_pw, node_dir / 'node_modules/playwright'], home=home, cwd=node_dir if node_dir.is_dir() else None, timeout=60)
    fix = f'Run {SKILL / "scripts/cutroom"} repair --no-model'
    if platform.system() == 'Linux':
        fix += ' --with-system-deps (installs Linux browser libraries; may require sudo)'
    checks.append({'name': 'Playwright / Chromium / Canvas 2D', 'status': 'ok' if ok else 'fail',
                   'detail': out if ok else (err[-1800:] or 'private Node environment missing'), 'fix': fix if not ok else ''})
    cache = absolute(os.environ.get('HUGGINGFACE_HUB_CACHE', os.environ.get('HF_HUB_CACHE',
                     str(absolute(os.environ.get('HF_HOME', str(Path.home() / '.cache/huggingface'))) / 'hub'))))
    model_dir = cache / 'models--Systran--faster-whisper-large-v3-turbo' / 'snapshots'
    cached = model_dir.is_dir() and any((p / 'model.bin').exists() and (p / 'config.json').exists() for p in model_dir.iterdir())
    checks.append({'name': 'Whisper model cache', 'status': 'ok' if cached else 'warn',
                   'detail': str(model_dir) if cached else 'Not cached; first transcription needs a network download (~1.6 GB).', 'fix': ''})
    info = machine_info(home)
    if info['memory_gib'] is not None and info['memory_gib'] < 8:
        checks.append({'name': 'Memory', 'status': 'warn', 'detail': 'Under 8 GiB RAM: use a smaller Whisper model and shorter draft renders.', 'fix': ''})
    if info['free_disk_gib'] < 5:
        checks.append({'name': 'Disk space', 'status': 'warn', 'detail': 'Under 5 GiB free; model downloads and frame renders may run out of space.', 'fix': ''})
    result = {'version': VERSION['version'], 'ready': not any(c['status'] == 'fail' for c in checks),
              'cutroom_home': str(home), 'skill': str(SKILL), 'machine': info, 'transcription': native, 'checks': checks}
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f'Cutroom {VERSION["version"]} · {info["system"]} {info["architecture"]} · {info["cpu_cores"]} CPU cores · {info["memory_gib"] or "unknown"} GiB RAM · {info["free_disk_gib"]} GiB free')
        for c in checks:
            print(f'  [{c["status"].upper()}] {c["name"]}: {c["detail"]}')
            if c.get('fix'):
                print(f'      fix: {c["fix"]}')
        print(f'PY={py}\nSKILL={SKILL}\nCUTROOM_HOME={home}')
        print('READY' if result['ready'] else 'NOT READY: address the failed checks above.')
    return 0 if result['ready'] else 1


def selected_targets(args, home, *, required=False):
    explicit = []
    project = absolute(args.project).resolve() if args.project else None
    if project and not project.is_dir():
        raise SetupError(f'Project directory does not exist: {project}')
    agents = [name for name in ['claude', 'codex'] if getattr(args, name)]
    if project or agents:
        for agent in agents or ['claude', 'codex']:
            base = project / ('.' + agent) if project else absolute(os.environ.get('CLAUDE_CONFIG_DIR' if agent == 'claude' else 'CODEX_HOME', str(Path.home() / ('.' + agent))))
            explicit.append(base / 'skills/cutroom')
    explicit.extend(absolute(p) for p in getattr(args, 'destination', []) or [])
    if not explicit and args.command != 'install':
        if (SKILL / MARKER).is_file():
            explicit = [SKILL]
        else:
            state = read_json(home / STATE, {})
            explicit = [absolute(p) for p in state.get('targets', []) if (absolute(p) / MARKER).is_file()]
    if not explicit:
        if required:
            raise SetupError('Choose --codex, --claude or --project DIR, or run from an installed skill.')
        for agent, key in [('claude', 'CLAUDE_CONFIG_DIR'), ('codex', 'CODEX_HOME')]:
            explicit.append(absolute(os.environ.get(key, str(Path.home() / ('.' + agent)))) / 'skills/cutroom')
    result = []
    for dest in explicit:
        if dest.name != 'cutroom' or dest.parent.name != 'skills' or dest.is_symlink():
            raise SetupError(f'Unsafe skill destination (expected .../skills/cutroom, no symlink): {dest}')
        # Resolve parents but preserve the leaf so a symlink cannot redirect replacement/removal.
        dest = dest.parent.resolve() / dest.name
        if home == dest or home.is_relative_to(dest) or dest.is_relative_to(home / 'venv') or dest.is_relative_to(home / 'node'):
            raise SetupError(f'Skill and runtime directories overlap: {dest} and {home}')
        if dest not in result:
            result.append(dest)
    return result


def install_target(source, dest, files, source_commit=None, payload=None):
    if dest.exists() and not dest.is_dir():
        raise SetupError(f'Destination is not a directory: {dest}')
    if dest.exists() and not (dest / MARKER).is_file():
        skill_text = (dest / 'SKILL.md').read_text() if (dest / 'SKILL.md').is_file() else ''
        if not re.search(r'^name:\s*cutroom\s*$', skill_text, re.M):
            raise SetupError(f'Refusing to overwrite an unrelated directory: {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.cutroom-stage-', dir=dest.parent))
    backup = dest.parent / ('.cutroom-backup-' + uuid.uuid4().hex)
    moved = False
    try:
        if dest.exists():
            shutil.copytree(dest, stage, dirs_exist_ok=True, symlinks=True)
        old = read_json(dest / MARKER, {}) if dest.exists() else {}
        for name, sha in old.get('files', {}).items():
            rel = relative_file(name)
            path = stage / str(rel)
            linked = any(p.is_symlink() for p in [path, *path.parents] if p != stage and stage in p.parents)
            if name not in files and not linked and path.is_file() and digest(path) == sha:
                path.unlink()
        for name in files:
            rel = relative_file(name)
            path = stage / str(rel)
            for ancestor in [path, *path.parents]:
                if ancestor == stage:
                    break
                if ancestor.is_symlink():
                    raise SetupError(f'Refusing to write through a symlink in installed skill: {name}')
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, path)
        atomic_json(stage / MARKER, {'name': 'cutroom', 'schema': 1, 'version': read_json(source / 'setup/version.json')['version'], 'source_commit': source_commit, 'payload': payload, 'files': files})
        if dest.exists():
            os.replace(dest, backup)
            moved = True
        try:
            os.replace(stage, dest)
        except BaseException:
            if moved:
                os.replace(backup, dest)
                moved = False
            raise
        if moved:
            shutil.rmtree(backup)
        print(f'  Installed skill: {dest}')
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def install_system_tools(home):
    """Explicit missing-only package-manager convenience; never replace an existing tool."""
    missing = [name for name in ['ffmpeg', 'node', 'npm'] if not shutil.which(name)]
    venv_ok, _, _ = capture([sys.executable, '-c', 'import venv, ensurepip'])
    if not venv_ok:
        missing.append('python3-venv')
    if not missing:
        return
    if shutil.which('brew'):
        packages = []
        if 'ffmpeg' in missing:
            packages.append('ffmpeg')
        if 'node' in missing or 'npm' in missing:
            packages.append('node@24')
        if 'python3-venv' in missing:
            raise SetupError('This Python lacks venv/ensurepip. Install a complete Python 3.10–3.13 distribution and rerun setup.')
        run(['brew', 'install', *packages], home=home)
        if 'node' in missing or 'npm' in missing:
            ok, prefix, err = capture(['brew', '--prefix', 'node@24'])
            if not ok:
                raise SetupError(f'Cannot locate Homebrew Node 24: {err}')
            os.environ['PATH'] = str(Path(prefix) / 'bin') + os.pathsep + os.environ.get('PATH', '')
            print(f'  Node 24 installed. For future sessions, add {Path(prefix) / "bin"} to PATH or select it with your Node version manager. Shell config was not edited.')
    elif shutil.which('apt-get'):
        prefix = [] if os.geteuid() == 0 else ['sudo']
        if prefix and not shutil.which('sudo'):
            raise SetupError('Missing system tools need apt-get privileges. Run the printed package install as root or install sudo.')
        packages = []
        if 'ffmpeg' in missing:
            packages.append('ffmpeg')
        if 'node' in missing or 'npm' in missing:
            packages.extend(['nodejs', 'npm'])
        if 'python3-venv' in missing:
            packages.append('python3-venv')
        run([*prefix, 'apt-get', 'update'], home=home)
        run([*prefix, 'apt-get', 'install', '-y', *packages], home=home)
    else:
        raise SetupError('No Homebrew or apt-get found. Install missing tools manually: ' + ', '.join(missing))


def setup_runtime(home, args, source=SKILL):
    if args.install_system_tools:
        install_system_tools(home)
    checks = system_checks()
    failures = [c for c in checks if c['status'] == 'fail']
    if failures:
        raise SetupError('\n'.join(f'{c["name"]}: {c["detail"]}\n  fix: {c["fix"]}' for c in failures))
    py_dir, node_dir = home / 'venv', home / 'node'
    py = py_dir / 'bin/python'
    if py_dir.exists() and (py_dir.is_symlink() or not (py_dir / 'pyvenv.cfg').is_file()):
        raise SetupError(f'Refusing to change a non-venv directory: {py_dir}')
    if node_dir.exists():
        package = read_json(node_dir / 'package.json', {})
        if node_dir.is_symlink() or package.get('name') != 'cutroom':
            raise SetupError(f'Refusing to change an unrecognized Node runtime: {node_dir}')
    print(f'Shared runtime: {home}', flush=True)
    home.mkdir(parents=True, exist_ok=True)
    if not py.is_file():
        run([sys.executable, '-m', 'venv', py_dir], home=home)
    ok, out, err = capture([py, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'])
    if not ok:
        raise SetupError(f'Existing venv cannot start: {err}. Move only {py_dir} aside, then run repair; keep profiles/projects in place.')
    version = tuple(map(int, out.split('.')))
    if not tuple(VERSION['python_min']) <= version < tuple(VERSION['python_max_exclusive']):
        raise SetupError(f'Existing venv uses unsupported Python {out}; move only {py_dir} aside and rerun repair.')
    run([py, '-m', 'pip', 'install', '--upgrade', f'pip=={VERSION["pip"]}'], home=home)
    run([py, '-m', 'pip', 'install', '--upgrade', '--only-binary=:all:', '-r', source / 'setup/requirements.txt'], home=home)
    run([py, '-m', 'pip', 'check'], home=home)
    node_dir.mkdir(parents=True, exist_ok=True)
    for name in ['package.json', 'package-lock.json']:
        if (node_dir / name).is_symlink():
            raise SetupError(f'Refusing to overwrite symlink: {node_dir / name}')
        shutil.copy2(source / 'setup' / name, node_dir / name)
    run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], home=home, cwd=node_dir)
    cli = node_dir / 'node_modules/playwright/cli.js'
    if args.with_system_deps:
        if platform.system() != 'Linux':
            print('  --with-system-deps is only needed on Linux; skipped.')
        else:
            run(['node', cli, 'install-deps', 'chromium'], home=home)
    run(['node', cli, 'install', 'chromium'], home=home)
    if not args.no_model:
        run([py, '-c', "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')"], home=home)
    else:
        print('  Whisper model download skipped (--no-model).')
    if doctor(home, source=source):
        raise SetupError('Runtime verification failed. Skill files were not updated; run the printed fixes, then repair.')


@contextlib.contextmanager
def setup_lock(home):
    import fcntl
    home.mkdir(parents=True, exist_ok=True)
    with (home / '.setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SetupError(f'Another Cutroom setup process is using {home}. Retry after it finishes.') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def source_for_install(home):
    marker = read_json(SKILL / MARKER, {})
    owned = marker.get('files', {})
    missing = [name for name in owned if not (SKILL / str(relative_file(name))).is_file()]
    if not missing:
        return SKILL
    payload = marker.get('payload', '')
    if not re.fullmatch(r'[a-f0-9]{64}', payload):
        raise SetupError('Managed skill files are missing. Run cutroom update --no-model to restore the official package.')
    cached = home / 'packages' / payload / 'skill'
    for name, sha in owned.items():
        path = cached / str(relative_file(name))
        if not path.is_file() or path.is_symlink() or digest(path) != sha:
            raise SetupError('Skill recovery cache is missing or modified. Run cutroom update --no-model to restore the official package.')
    print('  Recovering missing managed skill files from the runtime package cache: ' + ', '.join(missing))
    return cached


def cache_payload(home, source, files):
    key = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    parent = home / 'packages'
    dest = parent / key
    if dest.exists():
        for name, sha in files.items():
            path = dest / 'skill' / name
            if not path.is_file() or path.is_symlink() or digest(path) != sha:
                raise SetupError(f'Modified recovery cache: {path}. Move only {dest} aside and rerun repair.')
        return key
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.package-', dir=parent))
    try:
        for name in files:
            path = stage / 'skill' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, path)
            if digest(path) != files[name]:
                raise SetupError(f'Skill source changed during packaging: {name}. Rerun setup after edits finish.')
        atomic_json(stage / 'manifest.json', {'name': 'cutroom', 'files': files})
        os.replace(stage, dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return key


def install(args, home):
    source = source_for_install(home)
    files = source_files(source)
    targets = selected_targets(args, home)
    if args.dry_run:
        print(f'DRY RUN: Cutroom {VERSION["version"]}; no files or settings changed.')
        print(f'Runtime: {home}; browsers: {env_for(home)["PLAYWRIGHT_BROWSERS_PATH"]}')
        print('System requirements: Python 3.10–3.13, Node 20–24 with npm, FFmpeg 6+ with libx264/AAC.')
        print('Runtime setup: skipped (--skill-only)' if args.skill_only else f'Runtime setup: pinned pip {VERSION["pip"]}, {pins()}, npm ci, Chromium launch verification.')
        print(f'System tool installation: {"missing tools only" if args.install_system_tools and not args.skill_only else "disabled"}')
        print(f'Whisper download: {"skipped" if args.no_model or args.skill_only else VERSION["model"] + " (~1.6 GB)"}')
        print(f'Linux browser system libraries: {"install requested" if args.with_system_deps else "check only; use --with-system-deps if missing"}')
        for target in targets:
            print(f'Skill target: {target} ({len(files)} managed files)')
        return 0
    with setup_lock(home):
        if not args.skill_only:
            setup_runtime(home, args, source)
        # A source checkout can be edited while dependency downloads are running.
        files = source_files(source)
        payload = cache_payload(home, source, files)
        packaged_source = home / 'packages' / payload / 'skill'
        source_commit = args.source_commit or read_json(SKILL / MARKER, {}).get('source_commit')
        for target in targets:
            install_target(packaged_source, target, files, source_commit, payload)
        state = read_json(home / STATE, {})
        previous = state.get('targets', [])
        state.update({'name': 'cutroom', 'schema': 1, 'targets': sorted(set(previous + list(map(str, targets))))})
        if not args.skill_only:
            state['runtime_version'] = VERSION['version']
        atomic_json(home / STATE, state)
    print('Skill files installed; runtime setup was skipped. Run doctor before editing.' if args.skill_only else 'Cutroom is ready. Start a new agent session to load the installed skill.')
    print('Maintenance: sh <installed-skill>/scripts/cutroom version | doctor | repair --no-model')
    return 0


def remove_legacy_pointer(dest, dry=False):
    dest = dest.resolve()
    codex = absolute(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve()
    if dest != codex / 'skills/cutroom':
        return
    agents = codex / 'AGENTS.md'
    if not agents.is_file() or agents.is_symlink():
        return
    original = agents.read_bytes()
    pattern = re.compile(rb'^<!-- cutroom:begin -->\r?\n([^\r\n]+)\r?\n<!-- cutroom:end -->(?:\r?\n)?', re.M)
    prefix = 'When the user wants a video edited (cut, trimmed, captioned, motion graphics, sound effects, reels/shorts), follow '
    def replace(match):
        try:
            body = match[1].decode('utf-8')
        except UnicodeDecodeError:
            return match[0]
        if body.startswith(prefix) and body.endswith('.'):
            pointer = absolute(body[len(prefix):-1]).resolve()
            if pointer == dest / 'SKILL.md':
                return b''
        return match[0]
    updated = pattern.sub(replace, original)
    if updated == original:
        return
    if dry:
        print(f'DRY RUN: remove the exact legacy Cutroom pointer from {agents}; retain all unrelated content.')
        return
    temp = agents.with_name('.AGENTS.cutroom-' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_bytes(updated)
        temp.chmod(agents.stat().st_mode & 0o777)
        os.replace(temp, agents)
    finally:
        temp.unlink(missing_ok=True)
    print(f'  Removed exact legacy pointer: {agents}')


def uninstall(args, home):
    targets = selected_targets(args, home, required=True)
    for dest in targets:
        if not dest.exists():
            print(f'  Already absent: {dest}')
            remove_legacy_pointer(dest, args.dry_run)
            continue
        marker = read_json(dest / MARKER)
        if not marker or marker.get('name') != 'cutroom' or marker.get('schema') != 1:
            raise SetupError(f'{dest} has no managed inventory. Reinstall with --skill-only first, then uninstall safely.')
        files = marker.get('files', {})
        remove_legacy_pointer(dest, args.dry_run)
        for name in files:
            relative_file(name)
        if args.dry_run:
            print(f'DRY RUN: remove unchanged managed files from {dest}; keep modified/unknown files and all shared runtime/profile/project data.')
            continue
        for name, sha in files.items():
            path = dest / str(relative_file(name))
            if any(p.is_symlink() for p in [path, *path.parents] if p != dest and dest in p.parents):
                print(f'  Preserved symlink: {path}')
                continue
            if path.is_file() and digest(path) == sha:
                path.unlink()
            elif path.exists():
                print(f'  Preserved modified file: {path}')
        (dest / MARKER).unlink()
        # Only remove empty directories; user data and locally modified files survive.
        directories = {dest / str(parent) for name in files for parent in relative_file(name).parents if str(parent) != '.'}
        for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            with contextlib.suppress(OSError):
                directory.rmdir()
        with contextlib.suppress(OSError):
            dest.rmdir()
        print(f'  Uninstalled managed skill files: {dest}')
    if not args.dry_run:
        state = read_json(home / STATE, {})
        state['targets'] = [p for p in state.get('targets', []) if p not in set(map(str, targets))]
        atomic_json(home / STATE, state)
    print(f'Shared runtime retained: {home}. Style profiles, memory and projects were preserved.')
    return 0


def extract_package(archive, directory):
    """Extract ordinary files only; reject traversal, links, devices, duplicates and bombs."""
    total, seen = 0, set()
    def destination(name, size):
        nonlocal total
        rel = PurePosixPath(name)
        if not name or '\\' in name or rel.is_absolute() or '..' in rel.parts or any(':' in p for p in rel.parts):
            raise SetupError(f'Unsafe archive member: {name!r}')
        normalized = rel.as_posix()
        if len(rel.parts) > 32 or normalized in seen:
            raise SetupError(f'Duplicate or excessively deep archive member: {name!r}')
        seen.add(normalized)
        total += size
        if size < 0 or total > MAX_EXPANDED or len(seen) > 10000:
            raise SetupError('Update package exceeds the extraction limits.')
        return directory.joinpath(*rel.parts)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                mode = member.external_attr >> 16
                kind = mode & 0o170000
                if kind not in {0, 0o040000, 0o100000}:
                    raise SetupError(f'Archive links/special files are forbidden: {member.filename}')
                dest = destination(member.filename, member.file_size)
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(member) as src, dest.open('wb') as out:
                        shutil.copyfileobj(src, out)
                    dest.chmod(0o755 if mode & 0o111 else 0o644)
    else:
        with tarfile.open(archive, mode='r:*') as package:
            for member in package:
                if not member.isfile() and not member.isdir():
                    raise SetupError(f'Archive links/special files are forbidden: {member.name}')
                dest = destination(member.name, member.size)
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with package.extractfile(member) as src, dest.open('wb') as out:
                        shutil.copyfileobj(src, out)
                    dest.chmod(0o755 if member.mode & 0o111 else 0o644)
    candidates = [p.parent for p in directory.rglob('SKILL.md') if (p.parent / 'setup/version.json').is_file()]
    if len(candidates) != 1:
        raise SetupError('Update archive must contain exactly one self-contained Cutroom skill.')
    source_files(candidates[0])
    return candidates[0]


class HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urllib.parse.urlparse(newurl).scheme != 'https':
            raise SetupError('Refusing a download redirected away from HTTPS.')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def open_https(url, home):
    context = ssl.create_default_context()
    # Python.org macOS builds may need the installed runtime's CA bundle.
    for ca in (home / 'venv/lib').glob('python*/site-packages/certifi/cacert.pem'):
        context.load_verify_locations(cafile=str(ca))
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), HttpsOnlyRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': f'cutroom/{VERSION["version"]}', 'Accept': 'application/vnd.github+json'})
    return opener.open(request, timeout=60)


def update(args, home):
    targets = selected_targets(args, home, required=True)
    custom = args.package is not None
    if custom != bool(args.sha256):
        raise SetupError('--package and --sha256 must be supplied together.')
    if custom and not re.fullmatch(r'[a-fA-F0-9]{64}', args.sha256):
        raise SetupError('--sha256 must be a 64-character SHA-256 digest obtained from a trusted source.')
    package = args.package
    if custom:
        parsed = urllib.parse.urlparse(package)
        if parsed.scheme and parsed.scheme != 'https':
            raise SetupError('Use a local archive path or an https:// package URL.')
    if args.dry_run:
        if custom:
            print(f'DRY RUN: verify SHA-256 {args.sha256.lower()}, safely unpack {package}, then install into:')
        else:
            print(f'DRY RUN: resolve official statiiiix/cutroom ref {args.ref!r} to an exact GitHub commit, safely unpack its HTTPS archive, then install into:')
        for target in targets:
            print(f'  {target}')
        print('No download or write performed. Existing profile/project data and global agent settings are preserved.')
        return 0
    commit = None
    if not custom:
        ref = urllib.parse.quote(args.ref, safe='')
        with open_https(f'https://api.github.com/repos/statiiiix/cutroom/commits/{ref}', home) as response:
            # API metadata must remain small; archive limits are handled separately.
            metadata = response.read(1024 * 1024 + 1)
            if len(metadata) > 1024 * 1024:
                raise SetupError('GitHub commit metadata exceeds 1 MiB.')
            commit = json.loads(metadata).get('sha')
        if not isinstance(commit, str) or not re.fullmatch(r'[a-f0-9]{40}', commit):
            raise SetupError('GitHub did not resolve the requested ref to an exact commit SHA.')
        print(f'Official Cutroom update: {args.ref} -> {commit}', flush=True)
        package = f'https://codeload.github.com/statiiiix/cutroom/tar.gz/{commit}'
    remote = urllib.parse.urlparse(package).scheme == 'https'
    with tempfile.TemporaryDirectory(prefix='cutroom-update-') as temp:
        temp = Path(temp)
        archive = temp / 'package'
        if remote:
            with open_https(package, home) as response, archive.open('wb') as out:
                size = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    size += len(chunk)
                    if size > MAX_ARCHIVE:
                        raise SetupError('Update archive exceeds 64 MiB.')
                    out.write(chunk)
        else:
            source = absolute(package)
            if source.stat().st_size > MAX_ARCHIVE:
                raise SetupError('Update archive exceeds 64 MiB.')
            shutil.copyfile(source, archive)
        if custom and digest(archive) != args.sha256.lower():
            raise SetupError('Update SHA-256 mismatch. Nothing was installed.')
        extracted = temp / 'extracted'
        extracted.mkdir()
        source = extract_package(archive, extracted)
        command = [sys.executable, source / 'setup/manage.py', 'install']
        for target in targets:
            command.extend(['--destination', target])
        if commit:
            command.extend(['--source-commit', commit])
        for flag in ['no_model', 'skill_only', 'with_system_deps', 'install_system_tools']:
            if getattr(args, flag):
                command.append('--' + flag.replace('_', '-'))
        run(command, home=home)
    return 0


def parser():
    result = argparse.ArgumentParser(description='Cutroom setup and maintenance (runs from a checkout or an installed skill).')
    sub = result.add_subparsers(dest='command', required=True)
    for name in ['install', 'repair', 'update', 'uninstall']:
        p = sub.add_parser(name)
        p.add_argument('--claude', action='store_true', help='select CLAUDE_CONFIG_DIR/skills/cutroom')
        p.add_argument('--codex', action='store_true', help='select CODEX_HOME/skills/cutroom')
        p.add_argument('--project', metavar='DIR', help='select project-local agent skills; directory must exist')
        p.add_argument('--destination', action='append', help=argparse.SUPPRESS)
        p.add_argument('--dry-run', action='store_true', help='show intended changes without downloading or writing')
        if name != 'uninstall':
            p.add_argument('--source-commit', help=argparse.SUPPRESS)
            p.add_argument('--install-system-tools', action='store_true', help='install missing tools with Homebrew/apt; never replace incompatible existing versions')
            p.add_argument('--no-model', action='store_true', help='skip pre-downloading Whisper; first transcription downloads it')
            p.add_argument('--skill-only', action='store_true', help='copy skill files without installing/verifying runtimes')
            p.add_argument('--with-system-deps', action='store_true', help='explicitly install Chromium Linux system libraries (may use sudo)')
        if name == 'update':
            p.add_argument('--ref', default='main', help='official GitHub branch/tag/commit to resolve; default: main')
            p.add_argument('--package', help='custom trusted local archive or HTTPS URL; requires --sha256')
            p.add_argument('--sha256', help='expected digest from a trusted source; required with --package')
    p = sub.add_parser('doctor', help='check actual machine/runtime/browser capabilities; nonzero means not ready')
    p.add_argument('--json', action='store_true')
    sub.add_parser('version', help='show packaged and shared runtime versions without network access')
    return result


def main():
    args = parser().parse_args()
    home = runtime_home()
    if args.command == 'version':
        state = read_json(home / STATE, {})
        marker = read_json(SKILL / MARKER, {})
        if marker.get('source_commit'):
            print(f'Source commit {marker["source_commit"]}')
        print(f'Cutroom skill {VERSION["version"]}\nRuntime {state.get("runtime_version", "not installed by this setup")}\nSKILL={SKILL}\nCUTROOM_HOME={home}')
        return 0
    if args.command == 'doctor':
        return doctor(home, args.json)
    if args.command in {'install', 'repair'}:
        return install(args, home)
    if args.command == 'uninstall':
        if args.dry_run:
            return uninstall(args, home)
        with setup_lock(home):
            return uninstall(args, home)
    return update(args, home)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (SetupError, OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f'Cutroom setup failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
