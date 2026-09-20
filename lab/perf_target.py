"""Bounded HTTP fixture in an isolated Docker network; not an Internet speed server."""
import hashlib
import http.server
import json
import os
import ssl
import threading
from urllib.parse import parse_qs, urlsplit

BLOCK = os.urandom(65536)
MAX_BYTES = 16 * 1024 * 1024


def chunks(length):
    for start in range(0, length, len(BLOCK)):
        yield BLOCK[:min(len(BLOCK), length - start)]


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def send_body(self, body, status=200):
        self.send_response(status)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/latency':
            self.send_body(self.path.encode())
            return
        if parsed.path != '/download':
            self.send_body(b'not found', 404)
            return
        try:
            count = int(parse_qs(parsed.query)['bytes'][0])
            if not 1 <= count <= MAX_BYTES:
                raise ValueError()
        except (ValueError, KeyError):
            self.send_body(b'invalid size', 400)
            return
        digest = hashlib.sha256()
        for block in chunks(count):
            digest.update(block)
        self.send_response(200)
        self.send_header('Content-Length', str(count))
        self.send_header('X-Payload-SHA256', digest.hexdigest())
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            for block in chunks(count):
                self.wfile.write(block)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            size = int(self.headers['Content-Length'])
            if self.path != '/upload' or not 1 <= size <= MAX_BYTES:
                raise ValueError()
        except (ValueError, TypeError):
            self.send_body(b'invalid request', 400)
            return
        self.connection.settimeout(15)
        remaining = size
        digest = hashlib.sha256()
        while remaining:
            block = self.rfile.read(min(65536, remaining))
            if not block:
                return
            digest.update(block)
            remaining -= len(block)
        self.send_body(json.dumps({'bytes': size, 'sha256': digest.hexdigest()}).encode())

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    plain = http.server.ThreadingHTTPServer(('0.0.0.0', 18080), Handler)
    tls = http.server.ThreadingHTTPServer(('0.0.0.0', 18444), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(['h2', 'http/1.1'])
    context.load_cert_chain('/certs/server.crt', '/certs/server.key')
    tls.socket = context.wrap_socket(tls.socket, server_side=True)
    threading.Thread(target=tls.serve_forever, daemon=True).start()
    plain.serve_forever()
