from __future__ import annotations

import threading
import webbrowser
from http import HTTPStatus
from importlib.resources import files
from urllib.parse import urlparse

from factoria.application.agent_profiles import AgentRoleProfile, load_agent_profiles, save_agent_profile
from factoria.ui_agent_tools import _apply_agent_paths
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _HOST, _selected_project, _state
from factoria.web_n8n_patch import UI_PATCH


class FactoriaN8NHandler(FactoriaWebHandler):
    """Serve the n8n-style shell while reusing the existing local API."""

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            html = files("factoria.web").joinpath("index_n8n.html").read_text(encoding="utf-8")
            html = html.replace("</body>", UI_PATCH + "</body>")
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
        if path == "/api/state":
            if not self._authorized():
                self._json({"error": "unauthorized"}, 403)
                return
            payload = _extended_state()
            self._json(payload)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/agent-role/save":
            if not self._authorized():
                self._json({"error": "unauthorized"}, 403)
                return
            try:
                data = self._body()
                project = _selected_project(UiWorkspaceSettings.load())
                if project is None:
                    raise ValueError("Selecciona primero un proyecto")
                profile = AgentRoleProfile.from_mapping(data)
                saved = save_agent_profile(project, profile)
                self._json({"ok": True, "path": str(saved), "state": _extended_state()})
            except Exception as exc:
                self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
            return
        super().do_POST()


def _extended_state() -> dict[str, object]:
    payload = _state()
    project = _selected_project(UiWorkspaceSettings.load())
    platforms = list(payload.get("agents", []))
    payload["platforms"] = platforms
    payload["agent_roles"] = [item.to_mapping() for item in load_agent_profiles(project)]
    return payload


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
