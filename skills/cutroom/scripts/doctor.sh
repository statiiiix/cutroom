#!/bin/sh
# cutroom doctor: is this machine ready to edit? Prints what's missing and the exact fix.
#   sh doctor.sh            (exit 0 = ready)
PY="$HOME/.cutroom/venv/bin/python"
bad=0
ok() { printf '  ✓ %s\n' "$1"; }
no() { printf '  ✗ %s\n      fix: %s\n' "$1" "$2"; bad=1; }
command -v ffmpeg >/dev/null && ok "ffmpeg" || no "ffmpeg" "macOS: brew install ffmpeg · Ubuntu: sudo apt install ffmpeg"
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " zscale " && ok "ffmpeg zscale (HDR footage)" || printf '  ! ffmpeg has no zscale: iPhone HDR clips can not be tone-mapped (brew reinstall ffmpeg)\n'
command -v node >/dev/null && ok "node $(node -v)" || no "node" "macOS: brew install node · or https://nodejs.org"
[ -x "$PY" ] && ok "python venv ~/.cutroom/venv" || no "python venv" "sh install.sh (in the cutroom repo)"
[ -x "$PY" ] && "$PY" -c "import faster_whisper, numpy" 2>/dev/null && ok "faster-whisper + numpy" || no "faster-whisper" "sh install.sh"
[ -x "$PY" ] && "$PY" -c "import yt_dlp" 2>/dev/null && ok "yt-dlp (reference videos)" || printf '  ! yt-dlp missing: reference videos must be supplied as files\n'
ls "$HOME/.cache/huggingface/hub" 2>/dev/null | grep -qi "large-v3-turbo" && ok "whisper large-v3-turbo model cached" || printf '  ! whisper model not cached yet: the first transcription downloads it (~1.6 GB)\n'
[ -d "$HOME/.cutroom/node/node_modules/playwright" ] && ok "playwright" || no "playwright" "sh install.sh"
(cd "$HOME/.cutroom/node" 2>/dev/null && node -e "require('playwright').chromium.launch().then(b=>b.close()).then(()=>process.exit(0),()=>process.exit(1))" 2>/dev/null) \
  && ok "headless chromium launches" || no "headless chromium" "cd ~/.cutroom/node && npx playwright install chromium"
echo
echo "PY=$PY"
echo "SKILL=$(cd "$(dirname "$0")/.." && pwd)"
[ $bad = 0 ] && echo "READY" || echo "NOT READY: run the fixes above (or: sh install.sh from the cutroom repo)"
exit $bad
