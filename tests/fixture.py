"""Controlled destination only: stdlib HTTP/TLS and UDP echo, no proxy protocol."""
import http.server
import socketserver
import ssl
import threading


class HTTP(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = ('jp-proxy-target:' + self.path).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class UDP(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        sock.sendto(b'jp-proxy-target:' + data, self.client_address)


if __name__ == '__main__':
    plain_http = http.server.ThreadingHTTPServer(('0.0.0.0', 18080), HTTP)
    tls = http.server.ThreadingHTTPServer(('0.0.0.0', 18444), HTTP)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_alpn_protocols(['h2', 'http/1.1'])
    context.load_cert_chain('/certs/server.crt', '/certs/server.key')
    tls.socket = context.wrap_socket(tls.socket, server_side=True)
    udp = socketserver.ThreadingUDPServer(('0.0.0.0', 19000), UDP)
    for server in (plain_http, tls):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    udp.serve_forever()
