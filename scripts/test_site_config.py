import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from site_config import ROOT, settings, render, validate

class SiteConfigTests(unittest.TestCase):
    def setUp(self):
        self.values = settings(ROOT / '.env.example', environ={})

    def test_rejects_invalid_settings_before_writing(self):
        cases = [('PUBLIC_BIND_IP', '0.0.0.0'), ('HOST_TAILNET_IP', '192.0.2.1'),
                 ('AUTHENTIK_UPSTREAM_IP', '100.64.0.20\n}'), ('SSO_HOST', 'sso.example.com|.*'),
                 ('SSO_HOST', 'sso.example.com\nallow'), ('ANUBIS_PROTECTED_DOMAIN', '*.example.com'),
                 ('AUTHENTIK_UPSTREAM_PORT', '65536'), ('AUTHENTIK_UPSTREAM_PORT', '443 accept'),
                 ('AUTHENTIK_TLS_INSECURE', 'yes')]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'generated'
            for key, value in cases:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    render({**self.values, key: value}, output)
                self.assertFalse(output.exists())

    def test_missing_and_duplicate_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / '.env'
            path.write_text('SSO_HOST=sso.example.com\n')
            with self.assertRaises(ValueError): settings(path, environ={})
            path.write_text((ROOT / '.env.example').read_text() + '\nSSO_HOST=other.proxy.example.com\n')
            with self.assertRaises(ValueError): settings(path, environ={})

    def test_literal_quotes_and_shell_precedence(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / '.env'
            path.write_text((ROOT / '.env.example').read_text().replace('SSO_HOST=sso.proxy.example.com', "SSO_HOST='other.proxy.example.com'"))
            self.assertEqual(settings(path, environ={})['SSO_HOST'], 'other.proxy.example.com')
            self.assertEqual(settings(path, environ={'SSO_HOST': 'override.proxy.example.com'})['SSO_HOST'], 'override.proxy.example.com')

    def test_render_preserves_scope_and_unchanged_mount_inode(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            render(self.values, output)
            policy = (output / 'policy/icpm-web.nft').read_text()
            self.assertIn('ip daddr 192.0.2.10 tcp dport 443 accept', policy)
            self.assertIn('policy drop', policy)
            anubis = (output / 'anubis/botPolicies.yaml').read_text()
            self.assertIn('^sso[.]proxy[.]example[.]com[.]?(?::443)?$', anubis)
            caddy = output / 'authentik-outpost.Caddyfile'
            self.assertNotIn('tls_insecure_skip_verify', caddy.read_text())
            inode = caddy.stat().st_ino
            render(self.values, output)
            self.assertEqual(inode, caddy.stat().st_ino)
            render({**self.values, 'AUTHENTIK_TLS_INSECURE': 'true'}, output)
            self.assertIn('tls_insecure_skip_verify', caddy.read_text())

class SingleEnvTests(unittest.TestCase):
    def test_compose_maps_credentials_without_cross_instance_leaks(self):
        pairs = {}
        for prefix in ('ICPM', 'PCPM'):
            for key in ('SESSION_SECRET', 'ADMIN_USERNAME', 'ADMIN_PASSWORD', 'OAUTH_CLIENT_ID', 'OAUTH_CLIENT_SECRET', 'GEOIPUPDATE_ACCOUNT_ID', 'GEOIPUPDATE_LICENSE_KEY'):
                pairs[prefix + '_' + key] = prefix.lower() + '-' + key.lower() + '-fixture-!hash#literal'
        pairs.update(TS_AUTHKEY='tailnet-fixture', ANUBIS_PRIVATE_KEY_HEX='anubis-fixture')
        example = (ROOT / '.env.example').read_text()
        keys = {line.split('=', 1)[0] for line in example.splitlines() if '=' in line and not line.startswith('#')}
        self.assertTrue(set(pairs) <= keys)
        with tempfile.TemporaryDirectory() as temp:
            env_file = Path(temp) / '.env'
            lines = []
            for line in example.splitlines():
                key = line.split('=', 1)[0]
                lines.append(key + "='" + pairs[key] + "'" if key in pairs else line)
            env_file.write_text('\n'.join(lines) + '\n')
            result = subprocess.run(['docker', 'compose', '--env-file', str(env_file), '-f', str(ROOT / 'compose.yaml'), '--profile', '*', 'config', '--format', 'json'], cwd=ROOT, env={k:v for k,v in os.environ.items() if k not in keys}, check=True, capture_output=True, text=True)
            services = json.loads(result.stdout)['services']
        for name, service in services.items():
            self.assertNotIn('env_file', service)
            env = service.get('environment', {})
            for prefix in ('ICPM', 'PCPM'):
                expected_service = prefix.lower()
                for key in ('SESSION_SECRET', 'ADMIN_USERNAME', 'ADMIN_PASSWORD', 'OAUTH_CLIENT_ID', 'OAUTH_CLIENT_SECRET'):
                    value = pairs[prefix + '_' + key]
                    if name == expected_service + '-web':
                        self.assertEqual(env[key], value)
                    else:
                        self.assertNotIn(value, env.values())
                for key in ('GEOIPUPDATE_ACCOUNT_ID', 'GEOIPUPDATE_LICENSE_KEY'):
                    value = pairs[prefix + '_' + key]
                    if name == expected_service + '-geoipupdate':
                        self.assertEqual(env[key], value)
                    else:
                        self.assertNotIn(value, env.values())
            for var, key, target in [('TS_AUTHKEY', 'TS_AUTHKEY', 'tailscale'), ('ANUBIS_PRIVATE_KEY_HEX', 'ED25519_PRIVATE_KEY_HEX', 'pcpm-anubis')]:
                if name == target:
                    self.assertEqual(env[key], pairs[var])
                else:
                    self.assertNotIn(pairs[var], env.values())

class PublishScanTests(unittest.TestCase):
    def test_removed_secret_remains_detected_in_history(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / 'scripts').mkdir()
            shutil.copy(ROOT / 'scripts/scan-publish.py', repo / 'scripts')
            app = repo / 'apps/caddy-proxy-manager'
            app.mkdir(parents=True)
            def git(where, *args):
                return subprocess.run(['git', *args], cwd=where, check=True, capture_output=True)
            for where in (repo, app):
                git(where, 'init')
                git(where, 'config', 'user.name', 'Fixture')
                git(where, 'config', 'user.email', 'fixture@example.invalid')
            (app / 'README').write_text('fixture')
            git(app, 'add', '.'); git(app, 'commit', '-m', 'fixture')
            (repo / '.gitignore').write_text('.env\napps/\n')
            token = 'fixture-sensitive-' + '7' * 32
            (repo / '.env').write_text('SESSION_SECRET=' + token)
            (repo / 'accidental.txt').write_text(token)
            git(repo, 'add', '.'); git(repo, 'commit', '-m', 'fixture')
            git(repo, 'rm', 'accidental.txt'); git(repo, 'commit', '-m', 'remove file')
            result = subprocess.run(['python3', str(repo / 'scripts/scan-publish.py')], cwd=repo, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('infra:history:', result.stdout)
            self.assertNotIn(token, result.stdout + result.stderr)

if __name__ == '__main__': unittest.main()
