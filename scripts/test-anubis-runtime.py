#!/usr/bin/env python3
"""Exercise real Anubis configuration changes in an isolated disposable container."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = dict(algorithm='fast', difficulty=4, cookieHours=24, language='', simplified=False, robots=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='cpm-anubis-test-') as directory:
        root = Path(directory)
        control = root / 'control'
        control.mkdir(mode=0o777)
        control.chmod(0o777)  # Disposable test directory only; real volume is owned by UID 10001.
        policy = json.loads((ROOT / 'config/templates/anubis/botPolicies.json.tmpl').read_text().replace('@@SSO_HOST_REGEX@@', 'sso[.]example[.]test'))
        source = root / 'policy.json'
        source.write_text(json.dumps(policy))
        source.chmod(0o644)
        cid = subprocess.check_output([
            'docker', 'run', '-d', '--network', 'none', '--cap-drop', 'ALL', '--read-only', '--tmpfs', '/tmp',
            '--mount', f'type=bind,src={control},dst=/control',
            '--mount', f'type=bind,src={source},dst=/etc/anubis/botPolicies.json,readonly',
            '-e', 'BIND=127.0.0.1:8923', '-e', 'METRICS_BIND=:8925', '-e', 'TARGET=http://127.0.0.1:8924',
            '-e', 'REDIRECT_DOMAINS=*.example.test', '-e', 'ED25519_PRIVATE_KEY_HEX=' + secrets.token_hex(32),
            args.image,
        ], text=True).strip()

        def execute(code):
            return subprocess.check_output(['docker', 'exec', cid, 'bun', '-e', code], text=True)

        def apply(options, after=0):
            digest = hashlib.sha256(json.dumps(options, separators=(',', ':')).encode()).hexdigest()
            temp = control / 'request.tmp'
            temp.write_text(json.dumps(dict(hash=digest, options=options)))
            temp.chmod(0o644)
            temp.replace(control / 'desired.json')
            for _ in range(80):
                try:
                    status = json.loads((control / 'status.json').read_text())
                    if status['hash'] == digest and status['state'] == 'ready' and status.get('at', 0) >= after:
                        return digest
                    assert status.get('state') != 'error', 'Supervisor rejected valid options'
                except FileNotFoundError:
                    pass
                time.sleep(.25)
            raise AssertionError('Supervisor did not acknowledge applied options')

        try:
            apply(DEFAULTS)
            for algorithm in ('fast', 'slow', 'metarefresh'):
                options = dict(DEFAULTS, algorithm=algorithm, difficulty=2, cookieHours=48, language='ko', simplified=True, robots=True)
                digest = apply(options)
                actual = json.loads(execute("console.log(await Bun.file('/tmp/botPolicies.json').text())"))
                assert actual['bots'][0] == policy['bots'][0], 'Protocol exception changed'
                assert actual['bots'][-1]['challenge'] == dict(algorithm=algorithm, difficulty=2)
                env = json.loads(execute(r"""
                    const fs = require('fs');
                    for (const pid of fs.readdirSync('/proc').filter(x=>/^\d+$/.test(x))) {
                      try {
                        if(fs.readFileSync('/proc/'+pid+'/cmdline','utf8').split('\0')[0]!=='/ko-app/anubis')continue;
                        const env=Object.fromEntries(fs.readFileSync('/proc/'+pid+'/environ','utf8').split('\0').filter(Boolean).map(s=>{const i=s.indexOf('=');return [s.slice(0,i),s.slice(i+1)]}));
                        console.log(JSON.stringify(Object.fromEntries(['COOKIE_EXPIRATION_TIME','FORCED_LANGUAGE','USE_SIMPLIFIED_EXPLANATION','SERVE_ROBOTS_TXT'].map(k=>[k,env[k]]))));
                      } catch {}
                    }
                """))
                assert env == dict(COOKIE_EXPIRATION_TIME='48h', FORCED_LANGUAGE='ko', USE_SIMPLIFIED_EXPLANATION='true', SERVE_ROBOTS_TXT='true')
                robots = execute("const r=await fetch('http://127.0.0.1:8923/robots.txt',{headers:{host:'app.example.test','X-Real-IP':'198.51.100.5'}});console.log(await r.text())")
                assert 'Disallow: /' in robots
                print('PASS: runtime options applied for', algorithm, flush=True)
            invalid = dict(DEFAULTS, difficulty=99)
            (control / 'desired.json').write_text(json.dumps(dict(hash='invalid', options=invalid)))
            time.sleep(1)
            status = json.loads((control / 'status.json').read_text())
            assert status['hash'] == digest and status['state'] == 'ready', 'Invalid request replaced healthy settings'
            print('PASS: malformed runtime request retains last healthy settings', flush=True)
            apply(options)
            restarted_at = time.time() * 1000
            subprocess.run(['docker', 'restart', '--timeout', '10', cid], check=True, stdout=subprocess.DEVNULL)
            # Wait for a fresh supervisor heartbeat after restart, not an old ready file.
            time.sleep(1)
            apply(options, after=restarted_at)
            subprocess.run(['docker', 'exec', cid, '/ko-app/anubis', '--healthcheck'], check=True, capture_output=True)
            print('PASS: settings survive supervisor restart', flush=True)
        finally:
            subprocess.run(['docker', 'rm', '-f', cid], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
