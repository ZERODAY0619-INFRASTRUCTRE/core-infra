#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
"$ROOT/scripts/validate.sh"
APP="$ROOT/apps/caddy-proxy-manager"
REV=$(git -C "$APP" rev-parse --short=12 HEAD)
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$APP/package.json")
APP_VERSION="${VERSION}+tomori.${REV}"
case "${1:-all}" in
  all) set -- web caddy ;;
  web|caddy) set -- "$1" ;;
  *) echo "Usage: $0 [all|web|caddy]" >&2; exit 2 ;;
esac
# Build once per component without reading runtime secrets or restarting services.
for component in "$@"; do
  docker build --network "${CPM_BUILD_NETWORK:-default}" \
    --label "org.opencontainers.image.revision=$(git -C "$APP" rev-parse HEAD)" \
    --label "org.opencontainers.image.version=$APP_VERSION" \
    --build-arg "APP_VERSION=$APP_VERSION" \
    -f "$APP/docker/$component/Dockerfile" -t "cpm-$component:$REV" "$APP"
done
printf 'Set CPM_WEB_IMAGE=cpm-web:%s and CPM_CADDY_IMAGE=cpm-caddy:%s in .env\n' "$REV" "$REV"
printf 'Application version: %s\n' "$APP_VERSION"
