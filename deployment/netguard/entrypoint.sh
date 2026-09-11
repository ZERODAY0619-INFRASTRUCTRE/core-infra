#!/bin/sh
set -eu
# A new namespace has no app until this container becomes healthy.
# Replace only our table atomically; never flush Docker's DNS NAT table.
if nft list table inet cpm >/dev/null 2>&1; then
  { echo 'delete table inet cpm'; cat /etc/cpm/rules.nft; } > /tmp/rules.nft
else
  cat /etc/cpm/rules.nft > /tmp/rules.nft
fi
nft --check --file /tmp/rules.nft
nft --file /tmp/rules.nft
# Tailnet traffic uses the container gateway, not host Tailscale.
TAILNET_GATEWAY="${TAILNET_GATEWAY:-}"
if [ -n "$TAILNET_GATEWAY" ]; then
  ip route replace 100.64.0.0/10 via "$TAILNET_GATEWAY"
fi
if [ "${CERTIFICATE_EGRESS:-false}" = "true" ]; then
  python3 /certificate-egress.py --once
  python3 /certificate-egress.py &
fi
touch /tmp/cpm-ready
exec tail -f /dev/null
