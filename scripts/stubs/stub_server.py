"""Minimal HTTP stub for orchestrator pods that are not built in this branch.

It answers any ``*/ping`` path with ``pong`` (HTTP 200) so the Kubernetes
liveness/readiness probes and the Ingress routing checks pass, and answers
every other path with HTTP 404. It carries no business logic: the real
rf004/rf005 implementations live in their own branches and replace this
image when they are merged.
"""

import http.server
import socketserver


class PingHandler(http.server.BaseHTTPRequestHandler):
    """Return pong for */ping, 404 for everything else."""

    def _respond(self):
        path = self.path.split("?", 1)[0].rstrip("/")
        if path.endswith("/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"pong")
        else:
            self.send_response(404)
            self.end_headers()

    do_GET = _respond
    do_POST = _respond
    do_PUT = _respond
    do_DELETE = _respond

    def log_message(self, _format, *args):  # noqa: N802 (http.server API)
        """Keep the pod logs quiet."""


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", 8000), PingHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
