#!/usr/bin/env python3
"""Exercise real Caddy + Anubis in disposable containers; no production state.
Requires Docker, openssl and the locally built Caddy/Bun dependency images.
"""
import gzip
import base64
import socket
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
IMAGE = 'ghcr.io/techarohq/anubis@sha256:8828275668b7bc675679f100970f9714f731388fbbf66ae94de8aca952e3fc4a'
DOMAIN = 'proxy.example.com'

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()

def main():
    caddy = f'cpm-anubis-test-caddy-{os.getpid()}'
    anubis = f'cpm-anubis-test-filter-{os.getpid()}'
    websocket = f'cpm-anubis-test-ws-{os.getpid()}'
    with tempfile.TemporaryDirectory(prefix='cpm-anubis-test-') as tmp:
        work = Path(tmp)
        work.chmod(0o755)
        run('python3', str(ROOT / 'scripts/render-config.py'), '--env-file', str(ROOT / '.env.example'), '--output', str(work / 'generated'))
        module = ROOT / 'apps/caddy-proxy-manager/src/lib/caddy-anubis.ts'
        gate = json.loads(run('docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'bun',
            '-v', f'{module}:/tmp/gate.ts:ro', 'cpm-icpm-deps:local', '-e',
            f'import {{buildAnubisGate}} from "/tmp/gate.ts"; console.log(JSON.stringify(buildAnubisGate("{DOMAIN}")))'))
        run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
            '-subj', f'/CN=dashboard.{DOMAIN}', '-addext', f'subjectAltName=DNS:dashboard.{DOMAIN},DNS:sso.{DOMAIN},DNS:future.{DOMAIN}',
            '-keyout', f'{tmp}/key.pem', '-out', f'{tmp}/cert.pem')
        # Disposable test key only; the non-root Caddy container must read it.
        (work / 'key.pem').chmod(0o644)
        config = {
            'admin': {'listen': '127.0.0.1:2019'},
            'apps': {
                'tls': {'certificates': {'load_files': [{'certificate': '/test/cert.pem', 'key': '/test/key.pem'}]}},
                'http': {'servers': {
                    'front': {'listen': [':8443'], 'tls_connection_policies': [{'default_sni': f'dashboard.{DOMAIN}'}],
                        'automatic_https': {'disable_redirects': True}, 'routes': [*gate['routes'],
                            {'match': [{'path': ['/ws']}], 'handle': [{'handler': 'reverse_proxy', 'upstreams': [{'dial': '127.0.0.1:8990'}]}], 'terminal': True},
                            {'match': [{'host': [f'dashboard.{DOMAIN}', f'sso.{DOMAIN}', f'future.{DOMAIN}']}], 'handle': [{'handler': 'static_response',
                                'body': 'backend:{http.request.method}|{http.request.uri}|{http.request.body}|{http.request.scheme}'}]},
                            {'handle': [{'handler': 'static_response', 'body': 'backend:unrelated'}]}]},
                    'plain': {'listen': [':8080'], 'automatic_https': {'disable': True}, 'routes': gate['routes']},
                    'anubis_success': gate['successServer'],
                }},
            },
        }
        (work / 'config.json').write_text(json.dumps(config))
        try:
            run('docker', 'run', '-d', '--name', caddy, '-p', '127.0.0.1::8443', '-p', '127.0.0.1::8080',
                '-v', f'{tmp}:/test:ro', 'cpm-pcpm-caddy:local', 'caddy', 'run', '--config', '/test/config.json')
            run('docker', 'run', '-d', '--name', anubis, '--network', f'container:{caddy}',
                '--read-only', '--tmpfs', '/tmp', '--cap-drop', 'ALL',
                '-v', f'{work}/generated/anubis/botPolicies.yaml:/policy.yaml:ro',
                '-e', 'BIND=127.0.0.1:8923', '-e', 'TARGET=http://127.0.0.1:8924',
                '-e', 'METRICS_BIND=:8925', '-e', 'POLICY_FNAME=/policy.yaml',
                '-e', 'COOKIE_SECURE=true', '-e', 'COOKIE_PARTITIONED=false',
                '-e', f'REDIRECT_DOMAINS=*.{DOMAIN}', IMAGE)
            run('docker', 'run', '-d', '--name', websocket, '--network', f'container:{caddy}',
                '--entrypoint', 'bun', 'cpm-icpm-deps:local', '-e',
                'Bun.serve({port:8990,hostname:"127.0.0.1",fetch(r,s){if(s.upgrade(r))return;return new Response("upgrade required",{status:400})},websocket:{message(w,m){w.send(m)}}})')
            port = int(run('docker', 'port', caddy, '8443/tcp').rsplit(':', 1)[1])
            plain_port = int(run('docker', 'port', caddy, '8080/tcp').rsplit(':', 1)[1])
            # Only this disposable self-signed test endpoint disables TLS verification.
            context = ssl._create_unverified_context()
            cookies = SimpleCookie()

            def request(path='/', host=f'dashboard.{DOMAIN}', method='GET', body=None, extra=None, use_cookie=False, plain=False):
                connection = (http.client.HTTPConnection('127.0.0.1', plain_port, timeout=10) if plain else
                    http.client.HTTPSConnection('127.0.0.1', port, context=context, timeout=10))
                headers = {'Host': host, 'User-Agent': 'Mozilla/5.0 AnubisIntegrationTest', 'Accept-Encoding': 'gzip'}
                if use_cookie:
                    headers['Cookie'] = '; '.join(f'{k}={v.value}' for k,v in cookies.items())
                headers.update(extra or {})
                connection.request(method, path, body, headers)
                response = connection.getresponse()
                data = response.read()
                if response.getheader('Content-Encoding') == 'gzip':
                    data = gzip.decompress(data)
                for key, value in response.getheaders():
                    if key.lower() == 'set-cookie' and use_cookie:
                        cookies.load(value)
                result = response.status, dict((k.lower(),v) for k,v in response.getheaders()), data.decode(errors='replace')
                connection.close()
                return result

            for attempt in range(30):
                try:
                    status, _, html = request(use_cookie=True)
                    if status == 200 and '<script' in html and 'anubis_challenge' in html:
                        break
                except (OSError, http.client.HTTPException) as error:
                    if attempt == 29: print('Last request error:', error)
                time.sleep(0.2)
            else:
                raise AssertionError('Anubis challenge did not become ready: ' + str(locals().get('status')) + ' ' + str(locals().get('html', ''))[:200])
            assert status == 200 and 'backend:' not in html
            print('PASS: new client receives challenge, never backend')
            for host in [f'sso.{DOMAIN}', f'future.{DOMAIN}']:
                assert 'anubis_challenge' in request(host=host)[2]
            print('PASS: SSO browser and future wildcard hosts protected')
            for host in [f'dashboard.{DOMAIN}.', f'dashboard.{DOMAIN}:443', f'DASHBOARD.{DOMAIN.upper()}']:
                assert 'anubis_challenge' in request(host=host)[2], host
            print('PASS: hostname case, default port and trailing-dot forms protected')
            for headers in [
                {'X-Real-IP': '127.0.0.1', 'X-Anubis-Status': 'PASS', 'X-Cpm-Anubis-Verified': 'yes'},
                {'User-Agent': 'Googlebot', 'X-Forwarded-Host': f'sso.{DOMAIN}', 'X-Forwarded-Uri': '/application/o/token/'},
                {'X-Original-Uri': '/application/o/token/', 'Forwarded': 'for=127.0.0.1'},
            ]:
                assert 'anubis_challenge' in request(extra=headers)[2]
            print('PASS: fake identity, User-Agent and forwarding headers do not bypass')
            assert request(host='unrelated.example')[2].startswith('backend:')
            assert request('/keep?x=1', plain=True)[0] == 308
            assert request('/keep?x=1', plain=True)[1]['location'] == f'https://dashboard.{DOMAIN}/keep?x=1'
            print('PASS: unrelated host unaffected; HTTP redirects to HTTPS')
            for path in ['/application/o/token/', '/application/o/userinfo/', '/application/o/pcpm/jwks/',
                         '/application/o/pcpm/.well-known/openid-configuration']:
                assert request(path, host=f'sso.{DOMAIN}')[2].startswith('backend:'), path
                assert 'anubis_challenge' in request(path)[2], path
            for path in ['/api/v3/core/users/', '/application/o/authorize/', '/application/o/token/extra']:
                assert 'anubis_challenge' in request(path, host=f'sso.{DOMAIN}')[2], path
            print('PASS: only exact SSO protocol paths exempt; APIs and login remain protected')
            challenge = json.loads(re.search(r'<script[^>]*id="anubis_challenge"[^>]*>(.*?)</script>', html, re.S)[1])
            payload = challenge['challenge']
            nonce = 0
            started = time.monotonic()
            while True:
                digest = hashlib.sha256((payload['randomData'] + str(nonce)).encode()).hexdigest()
                if digest.startswith('0' * challenge['rules']['difficulty']):
                    break
                nonce += 1
            query = urlencode({'id': payload['id'], 'response': digest, 'nonce': nonce,
                'redir': f'https://dashboard.{DOMAIN}/after?x=1', 'elapsedTime': max(1, int((time.monotonic()-started)*1000))})
            status, headers, body = request('/.within.website/x/cmd/anubis/api/pass-challenge?' + query, use_cookie=True)
            assert status in (302,303,307), (status, body[:200])
            assert headers['location'] == f'https://dashboard.{DOMAIN}/after?x=1'
            assert any('auth' in k for k in cookies), list(cookies)
            status, headers, body = request('/after?x=1', use_cookie=True)
            assert body == 'backend:GET|/after?x=1||https', body
            assert headers.get('x-anubis-gate') == 'passed'
            print('PASS: real Proof-of-Work, cookie issuance and backend access')
            status, _, body = request('/submit?keep=%2F', method='POST', body='untouched=body', use_cookie=True)
            assert body == 'backend:POST|/submit?keep=%2F|untouched=body|https', body
            assert request('/spoof', use_cookie=True, extra={'X-Real-IP': '1.2.3.4'})[2].startswith('backend:')
            assert 'anubis_challenge' in request(extra={'Cookie': 'anubis-cookie-auth=forged'})[2]
            print('PASS: POST body, query and TLS context preserved; forged cookie rejected')
            # Verify an actual upgrade and bidirectional frame after the GET gate.
            with socket.create_connection(('127.0.0.1', port), timeout=10) as raw:
                with context.wrap_socket(raw, server_hostname=f'dashboard.{DOMAIN}') as ws:
                    key = base64.b64encode(os.urandom(16)).decode()
                    cookie = '; '.join(f'{k}={v.value}' for k,v in cookies.items())
                    handshake = (f'GET /ws HTTP/1.1\r\nHost: dashboard.{DOMAIN}\r\n'
                        f'User-Agent: Mozilla/5.0 AnubisIntegrationTest\r\nCookie: {cookie}\r\n'
                        f'Connection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: {key}\r\n\r\n')
                    ws.sendall(handshake.encode())
                    response = b''
                    while b'\r\n\r\n' not in response:
                        part = ws.recv(4096)
                        assert part, 'websocket closed before upgrade'
                        response += part
                    assert response.startswith(b'HTTP/1.1 101'), response[:200]
                    data, mask = b'hello', os.urandom(4)
                    ws.sendall(bytes([0x81, 0x80 | len(data)]) + mask + bytes(c ^ mask[i % 4] for i,c in enumerate(data)))
                    echo = b''
                    while len(echo) < 7:
                        part = ws.recv(7-len(echo))
                        assert part, 'websocket closed before echo'
                        echo += part
                    assert echo == b'\x81\x05hello', echo
            print('PASS: WebSocket upgrade and bidirectional frame through gate')
            assets = re.findall(r'(?:src|href)="(/\.within\.website/[^"?]+)', html)
            assert assets, 'no assets in challenge'
            for path in set(assets):
                assert request(path)[0] == 200, path
            print('PASS: challenge scripts and styles served on same host')
            logs = subprocess.run(['docker', 'logs', caddy], check=True, capture_output=True, text=True)
            assert f'*.{DOMAIN}' not in logs.stdout + logs.stderr, 'gate changed automatic TLS subjects'
            print('PASS: automatic HTTPS retains existing certificates without wildcard issuance')
            run('docker', 'stop', anubis)
            status, _, body = request(use_cookie=True)
            assert status >= 500 and 'backend:' not in body, (status, body)
            print('PASS: Anubis outage fails closed even with valid cookie')
        except Exception:
            for container in [websocket, anubis, caddy]:
                logs = subprocess.run(['docker','logs','--tail','8',container], capture_output=True,text=True)
                print(logs.stdout, logs.stderr)
            raise
        finally:
            for container in [websocket, anubis, caddy]:
                subprocess.run(['docker','rm','-fv',container], capture_output=True)

if __name__ == '__main__':
    main()
