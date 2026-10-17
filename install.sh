#!/bin/sh
# The same installer ships inside every installed skill; no checkout is needed for repair.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$ROOT/skills/cutroom/setup/install.sh" "$@"
