#!/usr/bin/env python3
"""Export only observed public peer endpoints; never node keys or identities."""
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'deployment/runtime/tailscale-peers.json'

def public_peers(status):
    result = {}
    if status.get('BackendState') != 'Running':
        return result
    for peer in status.get('Peer', {}).values():
        if not peer.get('Online') or not peer.get('Active') or peer.get('PeerRelay'):
            continue
        try:
            host, port = peer.get('CurAddr', '').rsplit(':', 1)
            if not 0 < int(port) <= 65535:
                continue
            ip = ipaddress.ip_address(host.strip('[]'))
            if not ip.is_global or ip.is_multicast or ip.is_unspecified or ip.is_loopback:
                continue
            for tail in peer.get('TailscaleIPs', []):
                parsed = ipaddress.ip_address(tail)
                if parsed.version == 4 and parsed in ipaddress.ip_network('100.64.0.0/10'):
                    result[str(parsed)] = str(ip)
        except (ValueError, TypeError):
            continue
    return result

def main():
    failed = False
    try:
        raw = subprocess.check_output(['docker','compose','-f',str(ROOT/'compose.yaml'),'exec','-T','tailscale','tailscale','status','--json'], timeout=7, stderr=subprocess.DEVNULL)
        peers = public_peers(json.loads(raw))
    except (subprocess.SubprocessError, ValueError, OSError):
        peers = {}
        failed = True
    now = int(time.time())
    try:
        old = json.loads(DEST.read_text())['snapshots']
        old = [s for s in old if now-180 <= s['at'] < now]
    except (OSError, ValueError, KeyError, TypeError):
        old = []
    if failed:
        old = []
    data = {'generated_at': now, 'snapshots': old + [{'at':now,'peers':peers}]}
    DEST.parent.mkdir(mode=0o750, exist_ok=True)
    os.chown(DEST.parent, 0, 10001)
    os.chmod(DEST.parent,0o750)
    temp = DEST.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o640), 'w') as f:
        os.fchmod(f.fileno(),0o640)
        os.fchown(f.fileno(),0,10001)
        json.dump(data,f)
    os.replace(temp,DEST)
    if failed:
        print('Tailscale observation failed; cleared endpoint observations')
        raise SystemExit(1)

if __name__ == '__main__':
    main()
