#!/bin/sh
# cutroom installer: turns Claude Code and Codex into a video-editing machine.
#
#   sh install.sh                      install for Claude Code AND Codex (whichever you have), plus all tools
#   sh install.sh --claude             Claude Code only   (~/.claude/skills/cutroom)
#   sh install.sh --codex              Codex only         (~/.codex/skills/cutroom)
#   sh install.sh --project <dir>      into one project   (<dir>/.claude/skills/cutroom and <dir>/.codex/skills/cutroom)
#   sh install.sh --no-model           skip pre-downloading the Whisper model (it downloads on first use instead)
#
# What it installs (safe to re-run; it updates in place):
#   ffmpeg + node (via Homebrew / apt when missing), a private Python env at ~/.cutroom/venv with faster-whisper,
#   numpy and yt-dlp, the Whisper large-v3-turbo model, and Playwright + headless Chromium at ~/.cutroom/node.
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
HOMEDIR="$HOME/.cutroom"
TARGETS=""; MODEL=1; PROJECT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --claude) TARGETS="$TARGETS claude" ;;
    --codex) TARGETS="$TARGETS codex" ;;
    --project) PROJECT="$(cd "$2" && pwd)"; shift ;;
    --no-model) MODEL=0 ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
  shift
done
[ -z "$TARGETS" ] && TARGETS="claude codex"

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok() { printf '  ✓ %s\n' "$1"; }
warn() { printf '  ! %s\n' "$1"; }
pkg() {  # install a system package with whatever is available
  if command -v brew >/dev/null; then brew install "$1"
  elif command -v apt-get >/dev/null; then sudo apt-get update -qq && sudo apt-get install -y "$2"
  else echo "Please install $1 yourself, then re-run."; exit 1; fi
}

say "1/5  System tools"
command -v ffmpeg >/dev/null || { warn "ffmpeg missing, installing"; pkg ffmpeg ffmpeg; }
ok "ffmpeg"
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " zscale " && ok "ffmpeg has zscale (HDR iPhone footage)" \
  || warn "this ffmpeg has no zscale: HDR (iPhone 'HDR Video') clips can't be tone-mapped. Homebrew's ffmpeg has it."
command -v node >/dev/null || { warn "node missing, installing"; pkg node nodejs; }
ok "node $(node -v)"
command -v python3 >/dev/null || { warn "python3 missing, installing"; pkg python3 python3; }
ok "python3 $(python3 -c 'import sys; print(sys.version.split()[0])')"

say "2/5  Python env ~/.cutroom/venv (faster-whisper, numpy, yt-dlp)"
mkdir -p "$HOMEDIR"
[ -x "$HOMEDIR/venv/bin/python" ] || python3 -m venv "$HOMEDIR/venv"
"$HOMEDIR/venv/bin/python" -m pip install -q --upgrade pip
"$HOMEDIR/venv/bin/python" -m pip install -q --upgrade -r "$REPO/requirements.txt"
ok "python packages installed"

if [ $MODEL = 1 ]; then
  say "3/5  Whisper large-v3-turbo (~1.6 GB, once)"
  KMP_DUPLICATE_LIB_OK=TRUE "$HOMEDIR/venv/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')" \
    && ok "model ready" || warn "model download failed; it will retry on first transcription"
else
  say "3/5  Whisper model: skipped (--no-model)"
fi

say "4/5  Playwright + headless Chromium (renders the graphics) → ~/.cutroom/node"
mkdir -p "$HOMEDIR/node"
cp "$REPO/package.json" "$HOMEDIR/node/package.json"
(cd "$HOMEDIR/node" && npm install --silent --no-audit --no-fund >/dev/null && npx --yes playwright install chromium >/dev/null) \
  && ok "playwright + chromium ready" || { echo "npm install failed in $HOMEDIR/node"; exit 1; }

say "5/5  Installing the skill"
install_to() {
  dest="$1/cutroom"; mkdir -p "$1"
  rm -rf "$dest.tmp"; cp -R "$REPO/skills/cutroom" "$dest.tmp"
  [ -d "$dest" ] && rm -rf "$dest"
  mv "$dest.tmp" "$dest"; ok "$dest"
}
for t in $TARGETS; do
  if [ -n "$PROJECT" ]; then base="$PROJECT/.$t/skills"
  elif [ "$t" = claude ]; then base="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
  else base="${CODEX_HOME:-$HOME/.codex}/skills"; fi
  install_to "$base"
done

# Codex builds without native skill loading still read ~/.codex/AGENTS.md: add a one-line pointer (once, marked)
case "$TARGETS" in *codex*)
  if [ -z "$PROJECT" ]; then
    AG="${CODEX_HOME:-$HOME/.codex}/AGENTS.md"; mkdir -p "$(dirname "$AG")"; touch "$AG"
    grep -q "cutroom:begin" "$AG" || { printf '\n<!-- cutroom:begin -->\nWhen the user wants a video edited (cut, trimmed, captioned, motion graphics, sound effects, reels/shorts), follow %s/skills/cutroom/SKILL.md.\n<!-- cutroom:end -->\n' "${CODEX_HOME:-$HOME/.codex}" >> "$AG"; ok "pointer added to $AG"; }
  fi ;;
esac

say "Checking"
sh "$REPO/skills/cutroom/scripts/doctor.sh" | sed -n '1,20p' || true

say "Done."
echo "  Start a NEW Claude Code or Codex session (skills load at session start) and say:"
echo
echo "    /cutroom edit ~/Desktop/clip1.mov ~/Desktop/clip2.mov"
echo
echo "  The first time, cutroom interviews you about your editing style and saves it, so it only asks once."
