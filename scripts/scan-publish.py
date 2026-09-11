#!/usr/bin/env python3
"""Check tracked files and reachable Git objects; never print matched values.
This is a focused known-value/token check, not a guarantee that all secrets are detected.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SECRET_KEY = re.compile(r'SECRET|PASSWORD|TOKEN|AUTHKEY|PRIVATE_KEY|LICENSE_KEY', re.I)
SITE_KEYS = {'PUBLIC_BIND_IP', 'HOST_TAILNET_IP', 'SSO_HOST', 'ANUBIS_PROTECTED_DOMAIN', 'AUTHENTIK_UPSTREAM_IP'}
# Immutable upstream Cypress fixture: test/cypress/fixtures/test.example.com-key.pem.
# Allow only this already-public test key, never arbitrary PEM files or paths.
PUBLIC_TEST_KEY_BLOBS = {"307cdc307be49b78be4004a754c74a9c2fdb344e"}
PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/]{40}'),
    re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{36,}\b'),
    re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{70,}\b'),
    # AWS's documented example access-key ID is public fixture data.
    re.compile(rb'\bAKIA(?!IOSFODNN7EXAMPLE\b)[0-9A-Z]{16}\b'),
    re.compile(rb'\bsk-ant-api\d+-[A-Za-z0-9_-]{40,}'),
]

def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo)

def env_values(path):
    result = {}
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.strip().partition('=')
            if sep and not key.startswith('#'):
                result[key.strip()] = value.strip().strip('\"\'')
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-env', action='append', type=Path, default=[])
    args = parser.parse_args()
    public_examples = set(env_values(ROOT / '.env.example').values())
    private_files = [ROOT / '.env', *(ROOT / 'deployment/secrets').glob('*.env'), *args.private_env]
    needles = set()
    for path in private_files:
        for key, value in env_values(path).items():
            if (SECRET_KEY.search(key) and len(value) >= 8) or (key in SITE_KEYS and value and value not in public_examples):
                needles.add(value.encode())
    issues, checked = set(), 0
    def inspect(data, location):
        nonlocal checked
        checked += 1
        oid = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if any(v in data for v in needles) or any(p.search(data) for i, p in enumerate(PATTERNS) if i != 0 or oid not in PUBLIC_TEST_KEY_BLOBS):
            issues.add(location)
    repos = [ROOT, ROOT / 'apps/caddy-proxy-manager']
    for repo in repos:
        prefix = 'infra' if repo == ROOT else 'app'
        for name in git(repo, 'ls-files', '-z').decode().strip('\0').split('\0'):
            path = repo / name
            if path.is_file():
                inspect(path.read_bytes(), prefix + ':tracked:' + name)
            if repo == ROOT:
                parts = Path(name).parts
                if any(p in parts for p in ('generated', 'runtime', 'backups', 'artifacts')) or name.endswith(('.bundle', '.db', '.key', '.pem')):
                    issues.add(prefix + ':forbidden-path:' + name)
                if (name.endswith('.env') and name not in ('config/common/web.env', 'config/icpm/web.env', 'config/pcpm/web.env')) or (Path(name).name.startswith('.env') and Path(name).name != '.env.example') or (name.startswith('deployment/secrets/') and not name.endswith('.example')):
                    issues.add(prefix + ':forbidden-path:' + name)
        objects = git(repo, 'rev-list', '--objects', '--all').splitlines()
        with subprocess.Popen(['git', 'cat-file', '--batch'], cwd=repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as proc:
            for entry in objects:
                oid = entry.split(b' ', 1)[0]
                proc.stdin.write(oid + b'\n'); proc.stdin.flush()
                header = proc.stdout.readline().split()
                data = proc.stdout.read(int(header[2])); proc.stdout.read(1)
                if header[1] in (b'blob', b'commit', b'tag'):
                    # Object hashes avoid leaking filenames or values from old history.
                    inspect(data, prefix + ':history:' + oid.decode())
            proc.stdin.close()
            proc.wait()
            if proc.returncode:
                raise SystemExit('Git object scan failed')
    if issues:
        print('FAIL: potential private content or forbidden paths (values omitted):')
        print('\n'.join(sorted(issues)))
        return 1
    print(f'PASS: {checked} tracked files/Git objects; no known private values, token patterns or private-key payloads')
    return 0

if __name__ == '__main__':
    sys.exit(main())
