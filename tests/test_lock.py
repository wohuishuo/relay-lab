import tempfile
import unittest
from pathlib import Path
from jp.common import state_lock


class LockTests(unittest.TestCase):
    def test_second_operation_rejected_and_lock_released(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            with state_lock(path):
                with self.assertRaises(RuntimeError):
                    with state_lock(path):
                        self.fail('Concurrent operation should not enter')
            with state_lock(path):
                self.assertTrue((path / '.operation.lock').exists())
