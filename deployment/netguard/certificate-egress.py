#!/usr/bin/env python3
"""Only grant certificate APIs HTTPS; keep old entries until TTL on DNS errors."""
import ipaddress
import socket
import subprocess
import sys
import time

HOSTS = ("acme-v02.api.letsencrypt.org",
         "acme-staging-v02.api.letsencrypt.org",
         "api.cloudflare.com")

def refresh():
    addresses = set()
    for hostname in HOSTS:
        answers = {x[4][0] for x in socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)}
        if not answers or any(not ipaddress.ip_address(ip).is_global for ip in answers):
            raise ValueError("Certificate endpoint did not resolve to public IPv4")
        addresses.update(answers)
    rules = ("flush set inet cpm cert_https4\n"
             "add element inet cpm cert_https4 { " +
             ", ".join(ip + " timeout 1h" for ip in sorted(addresses)) + " }\n")
    subprocess.run(["nft", "-f", "-"], input=rules, text=True, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Certificate API destination set refreshed", flush=True)

if "--once" in sys.argv:
    refresh()
else:
    while True:
        time.sleep(300)
        try:
            refresh()
        except Exception:
            print("Certificate DNS refresh failed; existing grants expire after one hour", flush=True)
