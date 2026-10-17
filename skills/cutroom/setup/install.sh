#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
  INSTALL_SYSTEM=0
  for ARG in "$@"; do
    [ "$ARG" = --install-system-tools ] && INSTALL_SYSTEM=1
    [ "$ARG" = --dry-run ] && INSTALL_SYSTEM=0 && break
  done
  if [ "$INSTALL_SYSTEM" = 1 ]; then
    if command -v brew >/dev/null 2>&1; then
      brew install python@3.12
      PYTHON_PREFIX=$(brew --prefix python@3.12)
      PATH="$PYTHON_PREFIX/libexec/bin:$PYTHON_PREFIX/bin:$PATH"
      export PATH
      echo "Python installed; select $PYTHON_PREFIX/libexec/bin in PATH for future sessions. Shell config was not edited."
    elif command -v apt-get >/dev/null 2>&1; then
      if [ "$(id -u)" = 0 ]; then
        apt-get update
        apt-get install -y python3 python3-venv
      else
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv
      fi
    fi
  fi
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Cutroom needs Python 3.10–3.13. Install python3, then rerun this command.' >&2
  exit 1
fi
# Keep the historical `sh install.sh --codex --no-model` syntax.
case "${1:-}" in
  install|repair|update|uninstall|doctor|version|-h|--help) exec python3 "$HERE/manage.py" "$@" ;;
  *) exec python3 "$HERE/manage.py" install "$@" ;;
esac
