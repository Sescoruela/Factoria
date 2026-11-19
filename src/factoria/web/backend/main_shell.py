from __future__ import annotations

from factoria.web.backend.server import FactoriaWebHandler, serve_web_ui


class FactoriaN8NHandler(FactoriaWebHandler):
    """Serve the main shell using the same local API and asset handler."""

    root_shell = "index_n8n.html"


def run_web_ui(*, open_browser: bool = True) -> int:
    return serve_web_ui(FactoriaN8NHandler, open_browser=open_browser)
