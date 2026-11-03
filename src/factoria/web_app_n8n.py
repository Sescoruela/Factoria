from __future__ import annotations

import threading
import webbrowser
from http import HTTPStatus
from importlib.resources import files
from urllib.parse import urlparse

from factoria.ui_agent_tools import _apply_agent_paths
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _HOST


class FactoriaN8NHandler(FactoriaWebHandler):
    """Serve the n8n-style shell while reusing the existing local API."""

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            html = files("factoria.web").joinpath("index_n8n.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        super().do_GET()


def run_web_ui(*, open_browser: bool = True) -> int:
    _apply_agent_paths()
    import secrets

    token = secrets.token_urlsafe(24)
    server = FactoriaHTTPServer((_HOST, 0), FactoriaN8NHandler)
    server.factoria_token = token
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/?token={token}"
    print(f"Factoria Web: {url}")
    if open_browser:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
