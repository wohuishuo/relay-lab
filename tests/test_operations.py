import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path


class OperationsTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('jp.operations'), 'operations API must exist')
        from jp import operations
        return operations

    def test_archive_rejects_traversal_and_links_before_extracting(self):
        o = self.api()
        for name, kind in [('../escape', 'file'), ('/escape', 'file'), ('ok/link', 'link')]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode='w') as archive:
                    item = tarfile.TarInfo(name)
                    if kind == 'link':
                        item.type, item.linkname = tarfile.SYMTYPE, '/etc/passwd'
                    archive.addfile(item)
                stream.seek(0)
                with self.assertRaises(ValueError):
                    o.extract_safe(stream, Path(temp) / 'restore')
                self.assertFalse((Path(temp) / 'restore').exists())

    def test_valid_archive_restores_and_refuses_existing_directory(self):
        o = self.api()
        with tempfile.TemporaryDirectory() as temp:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as archive:
                item = tarfile.TarInfo('a/config.json')
                item.size = 2
                archive.addfile(item, io.BytesIO(b'{}'))
            stream.seek(0)
            target = Path(temp) / 'restore'
            o.extract_safe(stream, target)
            self.assertEqual((target / 'a/config.json').read_bytes(), b'{}')
            stream.seek(0)
            with self.assertRaises(ValueError):
                o.extract_safe(stream, target)

    def test_failed_activation_preserves_current(self):
        o = self.api()
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'active.json').write_text('{"current":"old","previous":null}')
            def fail():
                raise RuntimeError('start failed')
            with self.assertRaises(RuntimeError):
                o.activate(state, 'new', fail)
            self.assertEqual(__import__('json').loads((state / 'active.json').read_text())['current'], 'old')

    def test_successful_activation_records_previous(self):
        o = self.api()
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'active.json').write_text('{"current":"old","previous":null}')
            o.activate(state, 'new', lambda: None)
            result = __import__('json').loads((state / 'active.json').read_text())
            self.assertEqual((result['current'], result['previous']), ('new', 'old'))

    def test_revoked_secret_reuse_is_rejected(self):
        o = self.api()
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            prior = '20260920T000000Z-abcdef12'
            (state / 'releases' / prior).mkdir(parents=True)
            from jp.config import example_secrets
            (state / 'releases' / prior / 'secrets.json').write_text(__import__('json').dumps(example_secrets()))
            (state / 'revoked-releases.json').write_text(__import__('json').dumps([prior]))
            settings = {'server':'node.example.com','domain':'node.example.com',
                        'reality_sni':'www.example.org','reality_dest':'www.example.org:443','protocols':['reality','hy2']}
            with self.assertRaisesRegex(ValueError, 'revoked'):
                o.prepare(state, settings, prior=prior)

if __name__ == '__main__':
    unittest.main()
