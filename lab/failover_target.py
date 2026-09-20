"""Local HTTPS health target with actual HTTP/1.1 ALPN support."""
import http.server
import socketserver
import ssl
import sys
import threading
sys.path.insert(0, '/tests')
from fixture import HTTP, UDP

plain = http.server.ThreadingHTTPServer(('0.0.0.0', 18080), HTTP)
secure = http.server.ThreadingHTTPServer(('0.0.0.0', 18444), HTTP)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version = ssl.TLSVersion.TLSv1_3
ctx.set_alpn_protocols(['http/1.1'])
ctx.load_cert_chain('/certs/server.crt', '/certs/server.key')
secure.socket = ctx.wrap_socket(secure.socket, server_side=True)
for server in (plain, secure):
    threading.Thread(target=server.serve_forever, daemon=True).start()
socketserver.ThreadingUDPServer(('0.0.0.0', 19000), UDP).serve_forever()
