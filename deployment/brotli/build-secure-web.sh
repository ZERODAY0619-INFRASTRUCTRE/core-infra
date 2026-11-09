#!/bin/sh
set -eu
script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_directory=$(CDPATH= cd -- "$script_directory/../.." && pwd)
source_directory="$root_directory/apps/caddy-proxy-manager"
python3 "$root_directory/scripts/app-source.py" check
revision=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["patched_tree"][:12])' "$root_directory/patches/caddy-proxy-manager/upstream.json")
# Security dependency pins are included in the exported source patch series.
docker build --network "${CPM_BUILD_NETWORK:-host}" \
  --label "org.opencontainers.image.revision=$revision" \
  --label "org.opencontainers.image.version=${APP_VERSION:-2.10.0+tomori.$revision}" \
  --build-arg "APP_VERSION=${APP_VERSION:-2.10.0+tomori.$revision}" \
  -f "$source_directory/docker/web/Dockerfile" \
  -t "${1:-cpm-web:$revision}" "$source_directory"
