#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 "$ROOT/scripts/app-source.py" prepare
python3 "$ROOT/scripts/render-config.py"
exec docker compose --env-file "$ROOT/.env" -f "$ROOT/compose.yaml" "$@"
