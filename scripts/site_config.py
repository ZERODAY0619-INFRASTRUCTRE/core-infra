"""Validated literal site settings for Compose and mounted configuration."""
import ipaddress
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent.parent
KEYS = ('PUBLIC_BIND_IP', 'HOST_TAILNET_IP', 'SSO_HOST', 'ANUBIS_PROTECTED_DOMAIN',
        'AUTHENTIK_UPSTREAM_IP', 'AUTHENTIK_UPSTREAM_PORT', 'AUTHENTIK_TLS_INSECURE')

def settings(env_file, environ=None):
    values = {}
    # Parse only site keys. Credentials remain exclusively in Compose's env files.
    for line in Path(env_file).read_text().splitlines():
        key, sep, value = line.strip().partition('=')
        if sep and key.strip() in KEYS:
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key in values:
                raise ValueError('Duplicate site setting: ' + key)
            values[key] = value
    environment = os.environ if environ is None else environ
    values.update({k: environment[k] for k in KEYS if k in environment})
    validate(values)
    return values

def validate(values):
    for key in KEYS:
        if not values.get(key):
            raise ValueError('Missing site setting: ' + key)
    for key in ('PUBLIC_BIND_IP', 'HOST_TAILNET_IP', 'AUTHENTIK_UPSTREAM_IP'):
        try:
            address = ipaddress.IPv4Address(values[key])
            if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local or str(address) == '255.255.255.255':
                raise ValueError()
            if key == 'HOST_TAILNET_IP' and address not in ipaddress.ip_network('100.64.0.0/10'):
                raise ValueError()
        except ValueError:
            raise ValueError('Invalid IPv4 setting: ' + key) from None
    for key in ('SSO_HOST', 'ANUBIS_PROTECTED_DOMAIN'):
        value = values[key]
        labels = value.split('.')
        if len(value) > 253 or len(labels) < 2 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
            raise ValueError('Invalid lowercase DNS hostname: ' + key)
    if not values['SSO_HOST'].endswith('.' + values['ANUBIS_PROTECTED_DOMAIN']):
        raise ValueError('SSO_HOST must be under ANUBIS_PROTECTED_DOMAIN')
    port = values['AUTHENTIK_UPSTREAM_PORT']
    if not re.fullmatch(r'[1-9][0-9]{0,4}', port) or int(port) > 65535:
        raise ValueError('Invalid port: AUTHENTIK_UPSTREAM_PORT')
    if values['AUTHENTIK_TLS_INSECURE'] not in ('true', 'false'):
        raise ValueError('AUTHENTIK_TLS_INSECURE must be true or false')

def render(values, output):
    validate(values)
    replacements = dict(values)
    replacements['SSO_HOST_REGEX'] = values['SSO_HOST'].replace('.', '[.]')
    replacements['AUTHENTIK_TLS_DIRECTIVE'] = ('tls_insecure_skip_verify' if values['AUTHENTIK_TLS_INSECURE'] == 'true' else '# TLS certificate verification enabled')
    rendered = []
    templates = ROOT / 'config/templates'
    for source in sorted(templates.rglob('*.tmpl')):
        content = source.read_text()
        for key, value in replacements.items():
            content = content.replace('@@' + key + '@@', value)
        if '@@' in content:
            raise ValueError('Unresolved template marker: ' + str(source.relative_to(ROOT)))
        rendered.append((source.relative_to(templates).with_suffix(''), content))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    for relative, content in rendered:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Unchanged files keep their inode for existing read-only container mounts.
        if target.is_file() and target.read_text() == content:
            continue
        with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, delete=False) as tmp:
            tmp.write(content)
            temp = Path(tmp.name)
        temp.chmod(0o644)
        temp.replace(target)
    return len(rendered)
