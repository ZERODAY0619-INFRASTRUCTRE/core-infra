#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "Usage: $0 NEW_UPSTREAM_TAG_OR_COMMIT" >&2; exit 2; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
[ -z "$(git -C "$ROOT" status --porcelain)" ] || { echo "Commit or stash infra changes first" >&2; exit 1; }
# A new ignored workspace preserves the current prepared source and every patch.
mkdir -p "$ROOT/apps"
WORK=$(mktemp -d "$ROOT/apps/cpm-update-XXXXXX")
git -C "$WORK" init -q
git -C "$WORK" fetch --no-tags https://github.com/fuomag9/caddy-proxy-manager.git "$1"
git -C "$WORK" checkout --detach FETCH_HEAD
git -C "$WORK" config user.name "CPM Patch Builder"
git -C "$WORK" config user.email "cpm-patch-builder@localhost"
set --
while IFS= read -r patch; do
  set -- "$@" "$ROOT/patches/caddy-proxy-manager/$patch"
done < "$ROOT/patches/caddy-proxy-manager/series"
# Ordinary conflicts stay in this workspace for manual review; no automatic resolution.
if ! git -C "$WORK" am --3way --keep-cr --whitespace=nowarn "$@"; then
  echo "Patch conflicts require review in $WORK" >&2
  exit 1
fi
echo "Candidate prepared at $WORK"
echo "Resolve conflicts with git add and git am --continue; commit any further changes, then run app-source.py export --source PATH --base FULL_UPSTREAM_SHA --version VERSION."
