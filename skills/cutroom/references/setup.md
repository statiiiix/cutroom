# Setup and maintenance

Every installed skill contains its installer, exact Python dependency set, npm lockfile,
version metadata and maintenance commands. Repair works after the original checkout is deleted.
Setup does not edit shell startup files, agent configuration or the style-profile lookup rules.

## Install

From the repository:

```sh
sh install.sh --dry-run --codex --no-model
sh install.sh --codex --no-model
# Both agents (the default):
sh install.sh --no-model
# Project-local skills; the project must already exist:
sh install.sh --project /absolute/path/to/project --no-model
```

`--claude` and `--codex` select targets. `--project DIR` installs both agents unless a
single agent is selected. `--no-model` skips the approximately 1.6 GB Whisper download;
transcription downloads the model on first use. Without it, model download/initialization
is required and a failure returns nonzero. Chromium is still downloaded and verified.
`--skill-only` copies skill files without installing or checking editing runtimes; run
`doctor` before editing. `--dry-run` performs no writes or downloads.

By default, missing system tools produce actionable instructions. Add `--install-system-tools`
to install missing tools with Homebrew/apt without changing an existing incompatible tool.
The bundled shell installer can bootstrap missing Python with that flag. No shell startup
files are edited. Homebrew Node 24 may need its printed PATH selection in future sessions;
older apt distributions may provide Node/FFmpeg below the supported minimum and require
a supported distribution package or version manager.

Install system prerequisites first, or use that flag: Python 3.10–3.13 with `venv`, Node.js 20/22/24 with npm,
and FFmpeg 6+ with libx264 and AAC. macOS 13+ and Debian/Ubuntu Linux on x86_64/arm64 are
supported. Native Python dependencies install from published wheels; unsupported platforms
fail rather than attempting a long source build. On macOS, `brew install ffmpeg node python@3.12`
provides system tools; ensure `python3` selects the supported Python. On Linux, use the
supported Node distribution and your distribution's FFmpeg, Python and python3-venv packages.
Older distribution FFmpeg packages may need an upgrade to meet the minimum.

Linux Chromium needs system libraries as well as its downloaded browser. The actual browser
launch is checked. Explicitly request those libraries with:

```sh
sh install.sh --codex --no-model --with-system-deps
```

This invokes the pinned Playwright CLI's `install-deps chromium` command on Linux and may
request sudo. Without the flag, missing browser libraries produce a failed readiness check
and an actionable repair command. Setup never hides an installation failure behind “ready.”

## Locations

| Setting | Default | Purpose |
| --- | --- | --- |
| `CUTROOM_HOME` | `~/.cutroom` | Shared `venv/`, `node/`, `browsers/`, package caches and setup registry |
| `CODEX_HOME` | `~/.codex` | Global Codex skill at `skills/cutroom` |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Global Claude skill at `skills/cutroom` |
| `PLAYWRIGHT_BROWSERS_PATH` | `$CUTROOM_HOME/browsers` | Explicit override for both setup and renderer |
| `HF_HOME` / `HF_HUB_CACHE` | Hugging Face defaults | Optional model-cache override; inherited by transcription |

Set these environment variables consistently for install, maintenance and editing. For example:

```sh
CUTROOM_HOME=/data/cutroom CODEX_HOME=/data/codex sh install.sh --codex --no-model
```

Project installs use `<project>/.codex/skills/cutroom` and/or `<project>/.claude/skills/cutroom`;
they share the selected runtime. Profile files retain the existing onboarding and lookup
behavior (`~/.cutroom/style.md`, brand profiles, project profiles and `CUTROOM_PROFILE`).
Changing the runtime location does not migrate or reset style memory.

## Maintain an installed skill

Use the actual installed path; these examples assume the default Codex location:

```sh
sh ~/.codex/skills/cutroom/scripts/cutroom version
sh ~/.codex/skills/cutroom/scripts/cutroom doctor
sh ~/.codex/skills/cutroom/scripts/cutroom doctor --json
sh ~/.codex/skills/cutroom/scripts/cutroom repair --no-model
sh ~/.codex/skills/cutroom/scripts/cutroom repair --no-model --with-system-deps
```

`doctor` reports OS/architecture, CPU cores, RAM, free disk, supported tool versions,
FFmpeg filters/encoders, exact Python package versions, dependency consistency, native
CPU transcription support, CUDA-device count and a real Chromium/Canvas 2D launch.
Exit 0 means required editing capabilities passed. Model-cache, low-memory, disk-space
and HDR `zscale` warnings describe optional or workload-dependent limitations. The model
check inspects local cache files without downloading or loading the large model. CUDA is
optional; CPU int8 is the baseline. GPU work additionally needs the NVIDIA libraries
required by CTranslate2 and a suitable device.

Repair reconciles the pinned runtime dependencies and reinstalls the current skill files.
A versioned recovery copy of managed skill files lives under `$CUTROOM_HOME/packages`;
when the installed maintenance entrypoint and manifests still work, repair can restore
deleted scripts/assets from that cache without the original checkout. The recovery cache
is retained on uninstall. If the entrypoint/manifests or recovery cache are unavailable,
rerun a fresh installer or use update to fetch the official package.
Run it from an installed skill to target that installation; pass agent/project flags to
select others. From a checkout, repair targets registered installations, or both default
agents if none are registered. A damaged venv that cannot start must be moved aside
individually before repair; never remove the whole runtime home to fix Python.

## Update

```sh
sh ~/.codex/skills/cutroom/scripts/cutroom update --no-model
# Select an official tag, branch or commit:
sh ~/.codex/skills/cutroom/scripts/cutroom update --ref main --no-model --dry-run
```

The default updater uses the official `statiiiix/cutroom` GitHub repository. It resolves
`main` (or `--ref`) through GitHub's API to an exact commit SHA, reports that commit, then
fetches the immutable commit archive over HTTPS. The new skill records its source commit
for `version`. A ref must contain the complete self-contained skill; older pre-0.2 archives
are rejected before installation. The default update becomes available once this setup is
present on the selected official ref.

For an advanced custom/offline package, choose a trusted archive and obtain its SHA-256
digest from a trusted source. Local archive paths and custom HTTPS URLs require both flags:

```sh
sh ~/.codex/skills/cutroom/scripts/cutroom update \
  --package /path/to/cutroom-release.tar.gz --sha256 <64-hex-digest> --no-model
```

A custom package can contain a repository ZIP/tar tree or just the self-contained skill.

Archives are limited in size, verified before use, and extracted into a temporary directory.
Traversal paths, links, devices and duplicate paths are rejected. The package must contain
exactly one complete Cutroom skill with consistent version/manifests. Treat release packages
as executable code; a custom-package checksum is useful only when its source is trusted. The new bundled
installer verifies its runtime before swapping skill files. Unknown files survive; shipped
managed files are replaced. Interrupted/failed directory replacement restores the old skill.
Each target replacement is atomic; a multi-target failure can leave earlier targets updated.

## Uninstall a target

```sh
sh ~/.codex/skills/cutroom/scripts/cutroom uninstall --dry-run
sh ~/.codex/skills/cutroom/scripts/cutroom uninstall
# Or select a target from another installation/checkout:
sh install.sh uninstall --project /absolute/path/to/project --codex
```

Removal deletes only unchanged files in that target's managed inventory. Modified files,
unknown files, projects, profiles and shared runtimes remain. It never deletes a shared
runtime when another agent target is removed. Older installations without an inventory
must first be reinstalled with `--skill-only`; this records managed files safely. For a selected global Codex installation, the exact legacy Cutroom pointer block is removed
from that Codex home’s `AGENTS.md`; all unrelated bytes are preserved. Custom/modified
pointers and pointers in a different Codex home remain for individual review.

The root and bundled Python manifests must match. Python runtime dependencies, including
transitive dependencies, have exact versions; npm uses `ci` and its integrity-checked lock.
Changing dependencies requires validating a clean isolated install and updating both copies.
