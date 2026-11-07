from __future__ import annotations

import threading
import webbrowser
from http import HTTPStatus
from importlib.resources import files
from urllib.parse import urlparse

from factoria.application.agent_profiles import AgentCatalogConflict, AgentRoleProfile, agent_catalog_snapshot, save_agent_profile
from factoria.application.project_integration import ProjectIntegration
from factoria.application.skill_catalog import SkillCatalogConflict, SkillDefinition, save_skill, skill_catalog_snapshot
from factoria.ui_agent_tools import _apply_agent_paths
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _HOST, _selected_project, _state
from factoria.web_n8n_patch import UI_PATCH


class FactoriaN8NHandler(FactoriaWebHandler):
    """Serve the n8n-style shell while reusing the existing local API."""

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == '/assets/skills.js':
            body = files('factoria.web').joinpath('skills.js').read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            html = files("factoria.web").joinpath("index_n8n.html").read_text(encoding="utf-8")
            html = html.replace("</body>", UI_PATCH + '<script src="/assets/skills.js"></script><script src="/assets/templates.js"></script><script src="/assets/resources.js"></script></body>')
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
        if path in {'/api/skill/create', '/api/skill/save'}:
            if not self._authorized():
                self._json({'error': 'unauthorized'}, 403)
                return
            try:
                data = self._body()
                project = _selected_project(UiWorkspaceSettings.load())
                if project is None:
                    raise ValueError('Selecciona primero un proyecto')
                if data.get('project_path') != str(project):
                    raise SkillCatalogConflict('El proyecto del borrador cambió; vuelve a cargarlo')
                if not isinstance(data.get('revision'), str):
                    raise ValueError('Falta la versión del catálogo; vuelve a cargar las skills')
                saved = save_skill(project, SkillDefinition.from_mapping(data), expected_revision=data['revision'],
                                   create=path.endswith('/create'))
                self._json({'ok': True, 'path': str(saved), 'state': _extended_state()})
            except SkillCatalogConflict as exc:
                self._json({'ok': False, 'error': str(exc)}, 409)
            except (ValueError, OSError) as exc:
                self._json({'ok': False, 'error': str(exc)}, 400)
            return
        if path == '/api/project/prepare':
            if not self._authorized():
                self._json({'error': 'unauthorized'}, 403)
                return
            try:
                data = self._body()
                project = _selected_project(UiWorkspaceSettings.load())
                if project is None:
                    raise ValueError('Selecciona primero un proyecto')
                service = ProjectIntegration(project)
                confirmed = data.get('confirmed') is True
                plan = service.apply(confirmed=True) if confirmed else service.plan()
                self._json({'ok': True, 'applied': confirmed, 'changed': list(plan.changed), 'conflicts': list(plan.conflicts), 'state': _extended_state()})
            except Exception as exc:
                self._json({'ok': False, 'error': str(exc)}, 400)
            return
        if path in {"/api/agent-role/save", "/api/agent-role/create"}:
            if not self._authorized():
                self._json({"error": "unauthorized"}, 403)
                return
            try:
                data = self._body()
                project = _selected_project(UiWorkspaceSettings.load())
                if project is None:
                    raise ValueError("Selecciona primero un proyecto")
                if data.get('project_path') != str(project):
                    raise AgentCatalogConflict('El proyecto seleccionado cambió; vuelve a cargar el editor')
                if not isinstance(data.get('revision'), str):
                    raise ValueError('Falta la versión del catálogo; vuelve a cargar el editor')
                profile = AgentRoleProfile.from_mapping(data)
                saved = save_agent_profile(project, profile, expected_revision=data['revision'],
                                           mode='create' if path.endswith('/create') else 'update')
                self._json({"ok": True, "path": str(saved), "state": _extended_state()})
            except AgentCatalogConflict as exc:
                self._json({"ok": False, "error": str(exc)}, 409)
            except Exception as exc:
                self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
            return
        super().do_POST()


def _extended_state() -> dict[str, object]:
    payload = _state()
    project = _selected_project(UiWorkspaceSettings.load())
    platforms = list(payload.get("agents", []))
    payload["platforms"] = platforms
    try:
        skills, revision, foreign = skill_catalog_snapshot(project)
        payload['skills'] = [skill.to_mapping() for skill in skills]
        payload['skill_catalog_revision'] = revision
        payload['unmanaged_skill_files'] = list(foreign)
    except (ValueError, OSError) as exc:
        payload['skills'] = []
        payload['skill_configuration_error'] = str(exc)
    try:
        agents, revision = agent_catalog_snapshot(project)
        payload["agent_roles"] = [item.to_mapping() for item in agents]
        payload['agent_catalog_revision'] = revision
    except (ValueError, OSError) as exc:
        payload['agent_roles'] = []
        payload['agent_configuration_error'] = str(exc)
    if project is not None:
        try:
            payload['integration'] = ProjectIntegration(project).check()
        except (ValueError, OSError) as exc:
            payload['integration'] = {'ready': False, 'error': str(exc)}
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
