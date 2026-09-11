#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
"$ROOT/scripts/validate.sh"
exec python3 "$ROOT/scripts/package-release.py"
