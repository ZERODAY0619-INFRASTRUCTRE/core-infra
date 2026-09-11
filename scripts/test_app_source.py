import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('app_source', ROOT / 'scripts/app-source.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)

class AppSourceTests(unittest.TestCase):
    def test_patch_reproduces_tree_and_refuses_unexported_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / 'patches', root / 'patches')
            saved = source.ROOT, source.PATCHES, source.APP
            source.ROOT = root
            source.PATCHES = root / 'patches/caddy-proxy-manager'
            source.APP = root / 'apps/caddy-proxy-manager'
            try:
                source.prepare(ROOT / 'apps/caddy-proxy-manager')
                expected = source.check()['patched_tree']
                source.prepare()  # Idempotent; does not double-apply.
                path = source.APP / 'package.json'
                path.write_text(path.read_text() + '\n')
                with self.assertRaises(ValueError): source.prepare()
                source.git(source.APP, 'add', 'package.json')
                source.git(source.APP, 'commit', '-m', 'test: retain a local source edit\n\nVerify that committed source changes survive patch export and reapply.')
                source.export(source.APP)
                self.assertNotEqual(expected, source.check()['patched_tree'])
                source.prepare(ROOT / 'apps/caddy-proxy-manager', replace=True)
                self.assertTrue(list((root / 'deployment/backups').iterdir()))
                source.check()
                patch = source.PATCHES / source.manifest()['patches'][0]['file']
                patch.write_bytes(patch.read_bytes() + b'\n')
                with self.assertRaises(ValueError): source.manifest()
            finally:
                source.ROOT, source.PATCHES, source.APP = saved

if __name__ == '__main__': unittest.main()
