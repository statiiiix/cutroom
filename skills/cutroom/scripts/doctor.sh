#!/bin/sh
# Exit 0 means editing capabilities passed; warnings describe optional capabilities.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$HERE/manage.py" doctor "$@"
