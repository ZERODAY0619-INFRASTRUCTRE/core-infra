#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "Usage: $0 APPROVED_COMMIT" >&2; exit 2; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
APP="$ROOT/apps/caddy-proxy-manager"
[ -z "$(git -C "$ROOT" status --porcelain)" ] || { echo "Commit or stash infra changes first" >&2; exit 1; }
REV=$(git -C "$APP" rev-parse --verify "$1^{commit}")
git -C "$APP" checkout --detach "$REV"
git -C "$ROOT" add apps/caddy-proxy-manager
"$ROOT/scripts/validate.sh"
echo "App pin staged. Run app checks/build, then review and commit the pin."
