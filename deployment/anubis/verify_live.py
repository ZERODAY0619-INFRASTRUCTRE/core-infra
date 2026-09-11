#!/usr/bin/env python3
"""Read-only public HTTPS smoke test; solves PoW without logging cookies/keys."""
import gzip
import hashlib
import http.client
from http.cookies import SimpleCookie
import json
import re
import ssl
import time
from urllib.parse import urlencode

import os

DOMAIN = os.environ['ANUBIS_PROTECTED_DOMAIN']

def main():
    for label in ('dashboard', 'sso'):
        host = f'{label}.{DOMAIN}'
        cookies = SimpleCookie()
        def request(path='/', use_cookie=True):
            connection = http.client.HTTPSConnection(host, timeout=20, context=ssl.create_default_context())
            headers = {'User-Agent': 'Mozilla/5.0 AnubisDeploymentVerification', 'Accept-Encoding': 'gzip'}
            if use_cookie:
                headers['Cookie'] = '; '.join(f'{k}={v.value}' for k,v in cookies.items())
            connection.request('GET', path, headers=headers)
            response = connection.getresponse()
            data = response.read()
            if response.getheader('Content-Encoding') == 'gzip':
                data = gzip.decompress(data)
            response_headers = {k.lower():v for k,v in response.getheaders()}
            for key, value in response.getheaders():
                if key.lower() == 'set-cookie' and use_cookie:
                    cookies.load(value)
            result = response.status, response_headers, data.decode(errors='replace')
            connection.close()
            return result
        status, headers, html = request()
        match = re.search(r'<script[^>]*id="anubis_challenge"[^>]*>(.*?)</script>', html, re.S)
        assert status == 200 and match, f'{host}: no challenge, HTTP {status}'
        challenge = json.loads(match[1])
        payload = challenge['challenge']
        start = time.monotonic()
        nonce = 0
        while True:
            digest = hashlib.sha256((payload['randomData']+str(nonce)).encode()).hexdigest()
            if digest.startswith('0' * challenge['rules']['difficulty']):
                break
            nonce += 1
        query = urlencode({'id': payload['id'], 'response': digest, 'nonce': nonce,
            'redir': f'https://{host}/', 'elapsedTime': max(1, int((time.monotonic()-start)*1000))})
        status, headers, _ = request('/.within.website/x/cmd/anubis/api/pass-challenge?' + query)
        assert status in (302,303,307) and headers.get('location') == f'https://{host}/', f'{host}: PoW failed'
        status, headers, body = request()
        assert status in (200,301,302,303,307,308) and headers.get('x-anubis-gate') == 'passed'
        assert not re.search(r'<script[^>]*id="anubis_challenge"', body)
        print(f'PASS: {host}: trusted HTTPS, challenge, real PoW and backend HTTP {status}')
        if label == 'sso':
            status, headers, body = request('/application/o/pcpm/.well-known/openid-configuration', use_cookie=False)
            assert status == 200 and headers.get('x-anubis-gate') == 'passed'
            assert json.loads(body).get('issuer')
            status, headers, body = request('/application/o/userinfo/', use_cookie=False)
            assert status in (401,403) and headers.get('x-anubis-gate') == 'passed'
            print('PASS: unauthenticated OIDC discovery available; UserInfo still requires authentication')

if __name__ == '__main__':
    main()
