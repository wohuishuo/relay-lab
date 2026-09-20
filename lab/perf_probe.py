"""HTTP proxy consumer only; Mihomo implements every proxy and transport protocol."""
import argparse
import hashlib
import http.client
import json
import os
import secrets
import socket
import time


def latency():
    conn = http.client.HTTPConnection('client', 17890, timeout=8)
    path = '/latency?nonce=' + secrets.token_hex(12)
    start = time.perf_counter()
    try:
        conn.request('GET', 'http://target:18080' + path)
        response = conn.getresponse()
        body = response.read(1024)
        return {'ok': response.status == 200 and body == path.encode(),
                'request_ms': round((time.perf_counter() - start) * 1000, 3)}
    except Exception as exc:
        return {'ok': False, 'error_type': type(exc).__name__}
    finally:
        conn.close()


def transfer(direction, count):
    conn = http.client.HTTPConnection('client', 17890, timeout=12)
    block = os.urandom(65536)
    digest = hashlib.sha256()
    start = time.perf_counter()
    try:
        if direction == 'upload':
            conn.putrequest('POST', 'http://target:18080/upload', skip_accept_encoding=True)
            conn.putheader('Content-Length', str(count))
            conn.endheaders()
            remaining = count
            while remaining:
                chunk = block[:min(remaining, len(block))]
                conn.send(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
                if time.perf_counter() - start > 45:
                    raise TimeoutError()
            response = conn.getresponse()
            result = json.loads(response.read(1024))
            ok = response.status == 200 and result == {'bytes': count, 'sha256': digest.hexdigest()}
            received = result.get('bytes', 0)
            first_byte = None
        else:
            conn.request('GET', f'http://target:18080/download?bytes={count}', headers={'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            first_byte = None
            received = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                if first_byte is None:
                    first_byte = time.perf_counter() - start
                received += len(chunk)
                digest.update(chunk)
                if received > count or time.perf_counter() - start > 45:
                    raise TimeoutError()
            ok = response.status == 200 and received == count and digest.hexdigest() == response.getheader('X-Payload-SHA256')
        seconds = time.perf_counter() - start
        return {'ok': ok, 'direction': direction, 'payload_bytes': received,
                'seconds': round(seconds, 6), 'mbps': received * 8 / seconds / 1e6 if ok else None,
                'first_chunk_ms': round(first_byte * 1000, 3) if first_byte is not None else None}
    except Exception as exc:
        return {'ok': False, 'direction': direction, 'error_type': type(exc).__name__,
                'seconds': round(time.perf_counter() - start, 6)}
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mib', type=int, default=2, choices=range(1, 17))
    parser.add_argument('--repeats', type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    # Readiness retries are recorded separately and not counted as performance samples.
    readiness = []
    for _ in range(20):
        item = latency()
        readiness.append(item)
        if item['ok']:
            break
        time.sleep(.25)
    samples = {'readiness': readiness, 'latency': [], 'transfers': []}
    for i in range(args.repeats):
        samples['latency'].append(latency())
        # Alternate direction order to reduce systematic warm-up bias.
        for direction in (['download', 'upload'] if i % 2 == 0 else ['upload', 'download']):
            samples['transfers'].append(transfer(direction, args.mib * 1024 * 1024))
    print(json.dumps(samples))
