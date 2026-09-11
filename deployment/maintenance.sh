#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

usage() {
  echo "Usage: $0 enable|disable|status|run -- COMMAND [ARGS...]" >&2
  exit 2
}

compose() {
  "$ROOT_DIR/scripts/compose.sh" "$@"
}

case "${1:-}" in
  enable)
    # Keep the flag in the process environment only; no secret or persistent
    # config is written. Recreating the web services applies the gate.
    MAINTENANCE_MODE=1 "$ROOT_DIR/scripts/compose.sh" up -d --force-recreate pcpm-web icpm-web
    ;;
  disable)
    MAINTENANCE_MODE=0 "$ROOT_DIR/scripts/compose.sh" up -d --force-recreate pcpm-web icpm-web
    ;;
  status)
    compose ps pcpm-web icpm-web
    ;;
  run)
    [ "${2:-}" = "--" ] || usage
    shift 2
    [ "$#" -gt 0 ] || usage
    cleanup() {
      MAINTENANCE_MODE=0 "$ROOT_DIR/scripts/compose.sh" up -d --force-recreate pcpm-web icpm-web >/dev/null
    }
    trap cleanup EXIT INT TERM
    MAINTENANCE_MODE=1 "$ROOT_DIR/scripts/compose.sh" up -d --force-recreate pcpm-web icpm-web
    "$@"
    ;;
  *) usage ;;
esac
