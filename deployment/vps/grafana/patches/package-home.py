"""Grafana resolves entrypoint aliases, so every patched asset needs matching hashes."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def load_patcher(name, filename):
    specification = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def integrity(content):
    return ' '.join(name + '-' + base64.b64encode(hashlib.new(name, content.encode()).digest()).decode()
                    for name in ('sha384', 'sha512'))


def package(directory):
    replacements = {}
    for filename, prefix, module in (
        ('56591.a0aa7fa32cd1074d.js', '56591', load_patcher('home_patch', 'patch-home.py')),
        ('18631.ceb2a2734f477243.js', '18631', load_patcher('core_patch', 'patch-core.py')),
    ):
        original = directory / filename
        content = module.patch(original.read_text()).split('//# sourceMappingURL=')[0]
        digest = hashlib.sha256(content.encode()).hexdigest()[:20]
        updated_name = f'{prefix}.{digest}.js'
        original.write_text(content)
        (directory / updated_name).write_text(content)
        replacements[filename] = (updated_name, content)
    runtime = directory / 'runtime.f6bd22711abefe1a.js'
    content = runtime.read_text().split('//# sourceMappingURL=')[0]
    if content.count('a0aa7fa32cd1074d') != 1:
        raise ValueError('Unexpected homepage reference in the runtime bundle.')
    for original, (updated, _) in replacements.items():
        content = content.replace(original.split('.')[1], updated.split('.')[1])
    digest = hashlib.sha256(content.encode()).hexdigest()[:20]
    runtime_name = f'runtime.{digest}.js'
    (directory / runtime_name).write_text(content)
    replacements[runtime.name] = (runtime_name, content)

    def rewrite(value):
        if isinstance(value, dict):
            source = value.get('src')
            rewritten = {key: rewrite(item) for key, item in value.items()}
            if isinstance(source, str):
                filename = Path(source).name
                if filename in replacements:
                    rewritten['integrity'] = integrity(replacements[filename][1])
            return rewritten
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, str):
            for original, (updated, _) in replacements.items():
                value = value.replace(original, updated)
        return value

    manifest_path = directory / 'assets-manifest.json'
    manifest = rewrite(json.loads(manifest_path.read_text()))
    manifest_path.write_text(json.dumps(manifest))
    for record in manifest.values():
        if isinstance(record, dict) and Path(record.get('src', '')).name in {
            filename for filename, _ in replacements.values()
        }:
            served_content = (directory / Path(record['src']).name).read_text()
            if record.get('integrity') != integrity(served_content):
                raise ValueError('Patched asset integrity does not match its manifest record.')


if __name__ == '__main__':
    package(Path(sys.argv[1]))
