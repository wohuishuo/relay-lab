import unittest
from jp.measurements import aggregate, mbps


class MeasurementsTests(unittest.TestCase):
    def test_units_use_payload_bytes_and_decimal_megabits(self):
        self.assertEqual(mbps(125000, 1), 1)
        self.assertEqual(mbps(1024 * 1024, 1), 8.388608)
        with self.assertRaises(ValueError):
            mbps(1, 0)

    def test_failed_transfers_are_not_zero_speed_or_silently_discarded(self):
        result = aggregate([{'ok': True, 'mbps': 10}, {'ok': False}, {'ok': True, 'mbps': 20}])
        self.assertEqual(result['successes'], 2)
        self.assertEqual(result['failures'], 1)
        self.assertEqual(result['median_mbps'], 15)
        self.assertFalse(result['all_passed'])
        self.assertIsNone(aggregate([{'ok': False}])['median_mbps'])
