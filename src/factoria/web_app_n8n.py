from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlparse

from factoria.web_app import FactoriaWebHandler, serve_web_ui


from factoria.web_shell import main_shell_html


class FactoriaN8NHandler(FactoriaWebHandler):
    """Serve the n8n-style shell while reusing the existing local API."""

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            html = main_shell_html()
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def run_web_ui(*, open_browser: bool = True) -> int:
    return serve_web_ui(FactoriaN8NHandler, open_browser=open_browser)
