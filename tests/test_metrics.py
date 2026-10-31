import json
from pathlib import Path
import tempfile
import unittest


class MetricsTests(unittest.TestCase):
    def test_projection_drops_commands_credentials_and_health_logs(self):
        from jp.metrics import container_summary
        record = {'Name': '/jp-proxy-mihomo-1', 'RestartCount': 2,
                  'Config': {'Env': ['TOKEN=must-never-be-recorded']},
                  'State': {'Pid': 1234, 'Running': True, 'OOMKilled': False,
                            'StartedAt': '2026-01-01T00:00:00Z',
                            'Health': {'Status': 'healthy', 'Log': ['must-never-be-recorded']}}}
        result = container_summary(record)
        self.assertNotIn('must-never-be-recorded', json.dumps(result))
        self.assertEqual(result['restarts'], 2)
        self.assertEqual(result['health'], 'healthy')

    def test_storage_stays_bounded_and_oversize_record_is_rejected(self):
        from jp.metrics import append_bounded
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for i in range(80):
                append_bounded(directory, {'sample': i, 'text': 'x' * 60}, max_bytes=256, files=3)
            logs = list(directory.glob('metrics*.jsonl'))
            self.assertLessEqual(len(logs), 3)
            self.assertLessEqual(sum(f.stat().st_size for f in logs), 768)
            for f in logs:
                for line in f.read_text().splitlines():
                    self.assertIsInstance(json.loads(line)['sample'], int)
            with self.assertRaises(ValueError):
                append_bounded(directory, {'text': 'x' * 300}, max_bytes=256, files=3)


if __name__ == '__main__':
    unittest.main()
