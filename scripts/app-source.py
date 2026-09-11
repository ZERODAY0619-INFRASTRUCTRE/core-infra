#!/usr/bin/env python3
"""Prepare and export an ordered Linux-style git-format-patch series."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PATCHES = ROOT / 'patches/caddy-proxy-manager'
APP = ROOT / 'apps/caddy-proxy-manager'


def git(path, *args, **kwargs):
    return subprocess.check_output(['git', *args], cwd=path, **kwargs)


def manifest():
    data = json.loads((PATCHES / 'upstream.json').read_text())
    if data['repository'] != 'https://github.com/fuomag9/caddy-proxy-manager.git':
        raise ValueError('Unexpected upstream repository')
    for key in ('commit', 'patched_tree'):
        if not re.fullmatch('[0-9a-f]{40}', data[key]): raise ValueError('Invalid ' + key)
    names = (PATCHES / 'series').read_text().splitlines()
    if names != [p['file'] for p in data['patches']] or not names:
        raise ValueError('series order differs from upstream.json')
    for index, patch in enumerate(data['patches'], 1):
        name = patch['file']
        if not re.fullmatch(rf'{index:04d}-[A-Za-z0-9][A-Za-z0-9-]*\.patch', name):
            raise ValueError('Invalid numbered patch filename')
        content = (PATCHES / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != patch['sha256']:
            raise ValueError('Patch checksum differs: ' + name)
        if not content.startswith(b'From ') or b'\nSubject: [PATCH ' not in content:
            raise ValueError('Expected a numbered git format-patch message: ' + name)
    cover = data['cover_letter']
    if cover != '0000-cover-letter.patch': raise ValueError('Invalid cover letter name')
    if hashlib.sha256((PATCHES / cover).read_bytes()).hexdigest() != data['cover_letter_sha256']:
        raise ValueError('Cover letter checksum differs')
    return data


def clean(path):
    if git(path, 'status', '--porcelain').strip():
        raise ValueError('App has uncommitted changes; commit reviewed changes before export')


def check(path=None):
    path = path or APP
    data = manifest()
    if not (path / '.git').exists(): raise ValueError('Run app-source.py prepare first')
    clean(path)
    if subprocess.run(['git', 'merge-base', '--is-ancestor', data['commit'], 'HEAD'], cwd=path).returncode:
        raise ValueError('Prepared source does not descend from the pinned upstream')
    if git(path, 'rev-parse', 'HEAD^{tree}').decode().strip() != data['patched_tree']:
        raise ValueError('Prepared source tree differs from the reviewed series')
    if int(git(path, 'rev-list', '--count', data['commit'] + '..HEAD')) != len(data['patches']):
        raise ValueError('Prepared source commit count differs from the series')
    return data


def prepare(source=None, replace=False):
    data = manifest()
    if APP.exists() and not replace:
        check();print('PASS: common source already matches the patch series');return
    APP.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cpm-prepare-', dir=APP.parent) as tmp:
        stage = Path(tmp) / 'source';stage.mkdir()
        git(stage, 'init', '-q')
        remote = str(source.resolve()) if source else data['repository']
        git(stage, 'fetch', '--quiet', '--no-tags', '--depth=1', remote, data['commit'])
        git(stage, 'checkout', '--quiet', '--detach', data['commit'])
        git(stage, 'config', 'user.name', 'CPM Patch Builder')
        git(stage, 'config', 'user.email', 'cpm-patch-builder@localhost')
        git(stage, 'am', '--quiet', '--keep-cr', '--committer-date-is-author-date', '--whitespace=nowarn',
            *[str(PATCHES / p['file']) for p in data['patches']])
        check(stage)
        if APP.exists():
            backup = ROOT / 'deployment/backups' / ('app-source-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            git_file = APP / '.git'
            if git_file.is_file():
                old_gitdir = git(APP, 'rev-parse', '--absolute-git-dir').decode().strip()
                git_file.write_text('gitdir: ' + old_gitdir + '\n')
            APP.rename(backup)
            print('Previous source preserved under deployment/backups/')
        stage.rename(APP)
    print('PASS: git am series reproduces the pinned source tree')


def export(source, base=None, version=None, require_signoff=False):
    data = manifest();source = source.resolve();clean(source)
    base = base or data['commit']
    if not re.fullmatch('[0-9a-f]{40}', base): raise ValueError('Use a full upstream commit SHA')
    if subprocess.run(['git', 'merge-base', '--is-ancestor', base, 'HEAD'], cwd=source).returncode:
        raise ValueError('Upstream base must be an ancestor of HEAD')
    commits = git(source, 'rev-list', '--reverse', base + '..HEAD').decode().splitlines()
    if not commits or git(source, 'rev-list', '--merges', base + '..HEAD').strip():
        raise ValueError('Export requires a nonempty linear commit series')
    for commit in commits:
        message = git(source, 'show', '-s', '--format=%B', commit).decode().strip()
        title, _, body = message.partition('\n\n')
        if len(title) > 75 or not re.fullmatch(r'[a-z0-9_-]+: .+[^.]', title) or not body.strip():
            raise ValueError('Use a subsystem: imperative subject (<=75 chars) and explanatory body')
        if require_signoff and not re.search(r'^Signed-off-by: .+ <[^<>]+>$', body, re.M):
            raise ValueError('Missing author DCO sign-off; add only after personal review')
    names = git(source, 'diff', '--name-only', base, 'HEAD').decode().splitlines()
    for name in names:
        p = Path(name)
        if (p.name.startswith('.env') and p.name != '.env.example') or p.suffix in ('.db', '.key', '.pem', '.p12', '.pfx'):
            raise ValueError('Refusing sensitive patch path: ' + name)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        git(source, 'format-patch', '--filename-max-length=120', '--binary', '--full-index', '--numbered', '--cover-letter',
            '--base=' + base, '--no-signature', '-o', str(stage), base + '..HEAD')
        cover = stage / '0000-cover-letter.patch'
        text = cover.read_text().replace('*** SUBJECT HERE ***', 'cpm: update deployment customizations').replace(
            '*** BLURB HERE ***', 'Apply the numbered patches in series order to the pinned public\nupstream commit. This series preserves the shared ICPM/PCPM behavior.\nReview each patch and run the deployment and application checks before\npublishing. No review, testing or DCO trailers are synthesized.')
        cover.write_text(text)
        # Preserve the previous patch set, including superseded filenames.
        backup = ROOT / 'deployment/backups' / ('patch-series-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        backup.mkdir(parents=True, mode=0o700)
        for old in PATCHES.glob('*.patch'): old.rename(backup / old.name)
        for p in stage.iterdir(): (PATCHES / p.name).write_bytes(p.read_bytes())
        files = sorted(p.name for p in stage.glob('*.patch') if not p.name.startswith('0000-'))
        (PATCHES / 'series').write_text('\n'.join(files) + '\n')
        data.update(commit=base, patched_tree=git(source, 'rev-parse', 'HEAD^{tree}').decode().strip(),
                    patches=[{'file':n,'sha256':hashlib.sha256((PATCHES/n).read_bytes()).hexdigest()} for n in files],
                    cover_letter_sha256=hashlib.sha256(cover.read_bytes()).hexdigest())
        if version: data['version'] = version
        (PATCHES / 'upstream.json').write_text(json.dumps(data, indent=2) + '\n')
    print('Numbered patch series exported; run scan-publish.py and prepare --replace')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare');p.add_argument('--source', type=Path);p.add_argument('--replace', action='store_true')
    commands.add_parser('check')
    p = commands.add_parser('export');p.add_argument('--source', type=Path, default=APP);p.add_argument('--base');p.add_argument('--version');p.add_argument('--require-signoff', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'prepare': prepare(args.source, args.replace)
        elif args.command == 'export': export(args.source, args.base, args.version, args.require_signoff)
        else: check();print('PASS: upstream, numbered patch hashes and prepared source tree')
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from None
