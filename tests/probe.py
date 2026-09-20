"""Black-box probes; only the upstream client implements proxy protocols."""
import argparse
import http.client
import json
import secrets
import socket
import sys
import time
import ssl
import hashlib


def tcp(host, target, timeout):
    path = '/' + secrets.token_hex(12)
    connection = http.client.HTTPConnection(host, 17890, timeout=timeout)
    try:
        connection.request('GET', 'http://' + target + ':18080' + path)
        response = connection.getresponse()
        return response.status == 200 and response.read(1024) == ('jp-proxy-target:' + path).encode()
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def udp(host, timeout):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        data = secrets.token_bytes(24)
        try:
            sock.sendto(data, (host, 19000))
            return sock.recvfrom(2048)[0] == b'jp-proxy-target:' + data
        except OSError:
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['tcp', 'udp', 'isolation', 'certificate'])
    parser.add_argument('--deny', action='store_true')
    parser.add_argument('--target', default='target')
    parser.add_argument('--wait-seconds', type=int, default=20)
    parser.add_argument('--tls-port', type=int)
    parser.add_argument('--fingerprint')
    args = parser.parse_args()
    if args.kind == 'certificate':
        context = ssl.create_default_context(cafile='/ca.crt')
        ok = False
        for _ in range(20):
            try:
                with socket.create_connection(('server', args.tls_port), timeout=2) as sock:
                    with context.wrap_socket(sock, server_hostname='node.test') as tls:
                        ok = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest() == args.fingerprint
                break
            except OSError:
                time.sleep(.25)
    elif args.kind == 'isolation':
        try:
            with socket.create_connection((args.target, 18080), timeout=2):
                ok = False
        except OSError:
            ok = True
    else:
        # Ensure a running local client, not a dead process, accounts for denial.
        ready = False
        for _ in range(20):
            try:
                with socket.create_connection(('client', 17890), timeout=1):
                    ready = True
                    break
            except OSError:
                time.sleep(.25)
        if not ready:
            print(json.dumps({'check': args.kind, 'passed': False, 'reason': 'client-not-ready'}))
            return 2
        deadline = time.monotonic() + args.wait_seconds
        successes = []
        while True:
            successes.append(tcp('client', args.target, 4) if args.kind == 'tcp' else udp('client', 3))
            if successes[-1] or args.deny or time.monotonic() >= deadline:
                break
            if not args.deny:
                time.sleep(.5)
        ok = not any(successes) if args.deny else any(successes)
    print(json.dumps({'check': args.kind, 'negative': args.deny, 'passed': ok}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
