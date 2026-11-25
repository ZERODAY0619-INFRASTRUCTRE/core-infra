#!/bin/sh
set -eu
script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_directory=$(CDPATH= cd -- "$script_directory/../.." && pwd)
source_directory="$root_directory/apps/caddy-proxy-manager"
security_source_directory="$script_directory/caddy-go-security"
python3 "$root_directory/scripts/app-source.py" check
revision=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["patched_tree"][:12])' "$root_directory/patches/caddy-proxy-manager/upstream.json")
if [ "$revision" != "d8ade7759fbe" ]; then
  echo "Review the Caddy security overrides against the new source revision before building." >&2
  exit 1
fi
image="${1:-cpm-caddy:$revision}"
temporary_source_directory=$(mktemp -d)
trap 'rm -rf -- "$temporary_source_directory"' 0
trap 'exit 1' 1 2 3 15
cp -a "$source_directory/." "$temporary_source_directory/"
for file in Dockerfile build.sh go.mod go.sum; do
  cp "$security_source_directory/$file" "$temporary_source_directory/docker/caddy/$file"
done
docker build --network "${CPM_BUILD_NETWORK:-host}" \
  --label "org.opencontainers.image.revision=$revision" \
  --label "org.opencontainers.image.version=${APP_VERSION:-2.11.1+tomori.$revision}" \
  --build-arg "APP_VERSION=${APP_VERSION:-2.11.1+tomori.$revision}" \
  -f "$temporary_source_directory/docker/caddy/Dockerfile" \
  -t "$image-base" "$temporary_source_directory"
docker build --network "${CPM_BUILD_NETWORK:-host}" \
  --build-arg "BASE_IMAGE=$image-base" \
  -f "$script_directory/caddy-runtime-security.Dockerfile" \
  -t "$image" "$script_directory"
