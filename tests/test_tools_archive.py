import io
import tarfile
import unittest

from jp.tools import read_binary


class ToolArchiveTests(unittest.TestCase):
    def test_same_named_directory_is_not_binary(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            directory = tarfile.TarInfo('age')
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
            executable = tarfile.TarInfo('age/age')
            executable.size = 3
            archive.addfile(executable, io.BytesIO(b'ELF'))
        data.seek(0)
        with tarfile.open(fileobj=data, mode='r:gz') as archive:
            self.assertEqual(read_binary(archive, 'age', 'linux'), b'ELF')

    def test_symbolic_link_is_not_binary(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as archive:
            link = tarfile.TarInfo('age')
            link.type = tarfile.SYMTYPE
            link.linkname = '/bin/sh'
            archive.addfile(link)
        data.seek(0)
        with tarfile.open(fileobj=data, mode='r:gz') as archive:
            with self.assertRaises(ValueError):
                read_binary(archive, 'age', 'linux')
