"""Path-prefix proxy that emulates the k8s_entrega2/zz-ingress.yml routing.

Binds 127.0.0.1:80 (requires root, like `minikube tunnel`) and forwards
requests by path prefix to the locally running app processes, exactly as
the Ingress resource does for the Minikube deployment:

    /users*  -> http://127.0.0.1:8000
    /posts*  -> http://127.0.0.1:8001
    /offers* -> http://127.0.0.1:8002
    /routes* -> http://127.0.0.1:8003
    /scores* -> http://127.0.0.1:8004
    /rf003*  -> http://127.0.0.1:8005
    /rf004*  -> http://127.0.0.1:8006
    /rf005*  -> http://127.0.0.1:8007

An upstream that is not listening (app scaled down / killed) answers
503, which mirrors the Ingress behaviour when a backend Service has no
ready endpoints.
"""

import os
import socket
import socketserver
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

# Port is configurable so the proxy can run without root (default 8080).
# Set PROXY_PORT=80 (and run as root) to mirror the Minikube Ingress exactly.
LISTEN = ("127.0.0.1", int(os.environ.get("PROXY_PORT", "8080")))

# Longest-prefix match, same order as zz-ingress.yml.
ROUTES = [
    ("/users", "http://127.0.0.1:8000"),
    ("/posts", "http://127.0.0.1:8001"),
    ("/offers", "http://127.0.0.1:8002"),
    ("/routes", "http://127.0.0.1:8003"),
    ("/scores", "http://127.0.0.1:8004"),
    ("/rf003", "http://127.0.0.1:8005"),
    ("/rf004", "http://127.0.0.1:8006"),
    ("/rf005", "http://127.0.0.1:8007"),
]

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class ProxyHandler(BaseHTTPRequestHandler):
    # HTTP/1.0 + Connection: close keeps the framing trivially correct:
    # every response is self-delimited and the socket is never reused,
    # so there is no way to emit duplicate Content-Length headers.
    protocol_version = "HTTP/1.0"
    server_version = "local-verify-proxy/1.0"

    def log_message(self, fmt, *args):  # noqa: N802
        sys.stderr.write("[proxy] %s %s\n" % (self.address_string(), fmt % args))

    def _send(self, status: int, body: bytes = b"", content_type: str = ""):
        self.send_response_only(status)
        self.send_header("Content-Type", content_type or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _forward(self):
        parts = urlsplit(self.path)
        upstream = None
        for prefix, base in ROUTES:
            if parts.path.startswith(prefix):
                upstream = base
                break
        if upstream is None:
            self._send(404, b"")
            return

        host = None
        try:
            host = socket.create_connection(
                (upstream.split("//")[1].split(":")[0], int(upstream.split(":")[2])),
                timeout=15,
            )
        except OSError:
            # Backend not running: same 503 the Ingress returns with no endpoints.
            self._send(503, b'{"msg": "no upstream"}')
            return

        try:
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower() not in HOP_BY_HOP
            }
            headers["Host"] = upstream.split("//")[1]

            body = b""
            length = self.headers.get("Content-Length")
            if length:
                body = self.rfile.read(int(length))
            elif self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                # Rare in this test suite; read nothing.
                body = b""

            host.sendall(
                (
                    f"{self.command} {self.path} HTTP/1.1\r\n"
                    + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                    + "\r\n"
                ).encode("latin-1")
            )
            if body:
                host.sendall(body)

            # Read the upstream response (status line + headers + body).
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = host.recv(65536)
                if not chunk:
                    break
                buf += chunk
            head, _, rest = buf.partition(b"\r\n\r\n")
            lines = head.decode("latin-1").split("\r\n")
            status = int(lines[0].split()[1])
            # Normalise header names to lowercase: uvicorn/h11 emit them in
            # lowercase and lookups must not be case-sensitive.
            resp_headers = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    if k.lower() not in HOP_BY_HOP:
                        resp_headers[k.lower()] = v.strip()

            if resp_headers.get("transfer-encoding", "").lower() == "chunked":
                # De-chunk the body.
                data = rest
                while True:
                    nl = data.find(b"\r\n")
                    if nl < 0:
                        break
                    size = int(data[:nl].split(b";")[0], 16)
                    if size == 0:
                        break
                    start = nl + 2
                    if len(data) < start + size:
                        need = start + size - len(data)
                        more = b""
                        while len(more) < need:
                            c = host.recv(65536)
                            if not c:
                                break
                            more += c
                        data += more
                    data = data[start + size + 2 :]
                body_out = data
            else:
                length = int(resp_headers.get("content-length", "0") or "0")
                while len(rest) < length:
                    chunk = host.recv(65536)
                    if not chunk:
                        break
                    rest += chunk
                body_out = rest[:length]

            content_type = resp_headers.get("content-type", "")
            self._send(status, body_out, content_type)
        except Exception as exc:  # pragma: no cover - defensive
            sys.stderr.write(f"[proxy] error forwarding: {exc}\n")
            try:
                self._send(502, b"")
            except Exception:
                pass
        finally:
            if host is not None:
                host.close()

    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_DELETE = _forward
    do_PATCH = _forward
    do_HEAD = _forward
    do_OPTIONS = _forward


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    server = ThreadingHTTPServer(LISTEN, ProxyHandler)
    print(f"[proxy] listening on http://{LISTEN[0]}:{LISTEN[1]}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
