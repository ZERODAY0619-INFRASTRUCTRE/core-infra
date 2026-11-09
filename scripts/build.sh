#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 "$ROOT/scripts/app-source.py" prepare
"$ROOT/scripts/validate.sh"
APP="$ROOT/apps/caddy-proxy-manager"
REV=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["patched_tree"][:12])' "$ROOT/patches/caddy-proxy-manager/upstream.json")
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROOT/patches/caddy-proxy-manager/upstream.json")
APP_VERSION="${VERSION}+tomori.${REV}"
case "${1:-all}" in
  all) set -- web caddy anubis ;;
  web|caddy|anubis) set -- "$1" ;;
  *) echo "Usage: $0 [all|web|caddy|anubis]" >&2; exit 2 ;;
esac
# Build once per component without reading runtime secrets or restarting services.
for component in "$@"; do
  if [ "$component" = web ]; then
    APP_VERSION="$APP_VERSION" "$ROOT/deployment/brotli/build-secure-web.sh" "cpm-web:$REV"
    continue
  fi
  if [ "$component" = caddy ]; then
    APP_VERSION="$APP_VERSION" "$ROOT/deployment/brotli/build-secure-caddy.sh" "cpm-caddy:$REV"
    continue
  fi
  image="cpm-$component:$REV"
  if [ "$component" = anubis ]; then
    image="cpm-anubis:$REV-base"
  fi
  docker build --network "${CPM_BUILD_NETWORK:-host}" \
    --label "org.opencontainers.image.revision=$(git -C "$ROOT" rev-parse HEAD)" \
    --label "org.opencontainers.image.version=$APP_VERSION" \
    --build-arg "APP_VERSION=$APP_VERSION" \
    -f "$APP/docker/$component/Dockerfile" -t "$image" "$APP"
  if [ "$component" = anubis ]; then
    docker build --network "${CPM_BUILD_NETWORK:-host}" \
      --build-arg "BASE_IMAGE=$image" \
      -f "$ROOT/deployment/brotli/anubis-secure.Dockerfile" \
      -t "cpm-anubis:$REV" "$ROOT/deployment/brotli"
  fi
done
printf 'Set CPM_WEB_IMAGE=cpm-web:%s and CPM_CADDY_IMAGE=cpm-caddy:%s in .env\n' "$REV" "$REV"
printf 'Set CPM_ANUBIS_IMAGE=cpm-anubis:%s in .env\n' "$REV"
printf 'Application version: %s\n' "$APP_VERSION"
