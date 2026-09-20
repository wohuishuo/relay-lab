"""Measurement arithmetic; failures remain visible and are never zero-speed samples."""
import statistics


def mbps(byte_count, seconds):
    if byte_count < 0 or seconds <= 0:
        raise ValueError('Positive duration and nonnegative payload size required')
    return byte_count * 8 / seconds / 1_000_000


def aggregate(rows):
    successful = [r['mbps'] for r in rows if r.get('ok')]
    return {'attempts': len(rows), 'successes': len(successful),
            'failures': len(rows) - len(successful),
            'all_passed': bool(rows) and len(rows) == len(successful),
            'median_mbps': statistics.median(successful) if successful else None,
            'min_mbps': min(successful) if successful else None,
            'max_mbps': max(successful) if successful else None}
