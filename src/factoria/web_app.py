from __future__ import annotations

import contextlib
import io
import json
import secrets
import subprocess
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlparse

from factoria.application.tool_presence import tool_presence, assert_ui_command_allowed
from factoria.application.setup import SetupService
from factoria.application.status import OperationalStatusService
from factoria.application.workflow_presets import (
    VisualWorkflowPreset,
    VisualWorkflowStep,
    default_preset,
    load_preset,
    save_preset,
    WorkflowCatalogConflict,
    workflow_catalog_snapshot,
    workflow_catalog_revision,
)
from factoria.config.loader import load_global_config
from factoria.ui_agent_tools import _apply_agent_paths, _load_agent_paths, _save_agent_paths
from factoria.ui_workspace import UiWorkspaceSettings, discover_projects, project_root

_HOST = "127.0.0.1"
_ALLOWED_COMMANDS = {
    "status",
    "history",
    "plugins",
    "memoria-init",
    "memoria-update",
    "pause",
    "cancel",
    "commit",
    "security",
}
_ASYNC_COMMANDS: set[str] = set()  # Provider execution belongs to the external tool session.
_JOBS: dict[str, dict[str, object]] = {}
_JOBS_LOCK = threading.Lock()


def _is_git_project(path: Path | None) -> bool:
    return bool(path and path.is_dir() and (path / ".git").exists())


def _selected_project(settings: UiWorkspaceSettings) -> Path | None:
    if settings.last_project is None:
        return None
    return project_root(settings.last_project, settings.projects_root)


def _project_payload(root: Path | None) -> dict[str, object] | None:
    if root is None:
        return None
    try:
        report = OperationalStatusService().inspect(root, include_history=True)
        return {
            "name": report.project_name,
            "path": str(root),
            "branch": report.branch,
            "dirty": report.dirty,
            "memory_initialized": report.memory_initialized,
            "profile": report.effective_profile,
            "tool": report.effective_tool,
            "warnings": list(report.warnings),
            "recommendations": list(report.recommendations),
            "active_flows": [asdict(item) for item in report.active_flows],
            "history": [asdict(item) for item in report.recent_results],
            "security": asdict(report.security),
        }
    except Exception as exc:
        return {"name": root.name, "path": str(root), "error": f"{type(exc).__name__}: {exc}"}


def _agent_payload() -> list[dict[str, object]]:
    persisted = _apply_agent_paths()
    return [{**item, 'configured_path': persisted.get(str(item['name']))} for item in tool_presence()]


def _job_summaries() -> list[dict[str, object]]:
    with _JOBS_LOCK:
        jobs = [dict(item) for item in _JOBS.values()]
    jobs.sort(key=lambda item: float(item.get("created_at", 0)), reverse=True)
    return jobs[:10]


def _workflow_payload(root: Path | None) -> dict[str, object]:
    if root is None:
        return {
            "feature": default_preset("feature").to_mapping(),
            "fix": default_preset("fix").to_mapping(),
        }
    try:
        presets, revision = workflow_catalog_snapshot(root)
        from factoria.application.agent_profiles import load_agent_profiles
        agents = [{'role': agent.role, 'base_role': agent.base_role, 'name': agent.name}
                  for agent in load_agent_profiles(root)]
        if revision != workflow_catalog_revision(root):
            raise WorkflowCatalogConflict('El catálogo de agentes cambió; vuelve a cargar los flujos')
        return {kind: {**preset.to_mapping(), 'revision': revision, 'agents': agents} for kind, preset in presets.items()}
    except (ValueError, OSError) as exc:
        return {kind: {'kind': kind, 'steps': [], 'error': str(exc)} for kind in ('feature', 'fix')}


def _state() -> dict[str, object]:
    settings = UiWorkspaceSettings.load()
    root = _selected_project(settings)
    projects = discover_projects(settings.projects_root) if settings.projects_root else ()
    global_config = load_global_config(Path.home() / ".factoria" / "config.toml")
    return {
        "projects_root": str(settings.projects_root) if settings.projects_root else None,
        "selected_project": _project_payload(root),
        "projects": [{"name": p.name, "path": str(p)} for p in projects],
        "agents": _agent_payload(),
        "default_tool": global_config.default_tool,
        "jobs": _job_summaries(),
        "workflows": _workflow_payload(root),
    }


def _set_projects_root(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    if not target.is_dir():
        raise ValueError("La carpeta raíz no es válida")
    current = UiWorkspaceSettings.load()
    last = current.last_project if current.last_project and current.last_project.exists() else None
    UiWorkspaceSettings(projects_root=target, last_project=last).save()
    return target


def _save_selected_project(path: Path) -> None:
    settings = UiWorkspaceSettings.load()
    selected = project_root(path, settings.projects_root)
    if selected is None:
        raise ValueError("La carpeta no pertenece a un proyecto Git")
    UiWorkspaceSettings(projects_root=settings.projects_root, last_project=selected).save()


def _set_default_tool(tool: str) -> Path:
    if tool not in {"codex", "opencode"}:
        raise ValueError("Agente no válido")
    service = SetupService()
    target = Path.home() / ".factoria" / "config.toml"
    return service.save_tool_preference(target, tool)


def _set_agent_path(tool: str, raw_path: str) -> Path:
    if tool not in {"codex", "opencode"}:
        raise ValueError("Agente no válido")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError("El ejecutable indicado no existe")
    paths = _load_agent_paths()
    paths[tool] = str(path)
    _save_agent_paths(paths)
    _apply_agent_paths()
    return path


def _create_project(name: str, purpose: str = "") -> Path:
    settings = UiWorkspaceSettings.load()
    if settings.projects_root is None:
        raise ValueError("Configura primero una carpeta raíz de proyectos")
    safe = "-".join(part for part in name.strip().lower().replace("_", "-").split() if part)
    if not safe or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-." for ch in safe):
        raise ValueError("Nombre de proyecto no válido")
    target = (settings.projects_root / safe).resolve()
    target.relative_to(settings.projects_root.resolve())
    if target.exists():
        raise ValueError("Ya existe una carpeta con ese nombre")
    target.mkdir(parents=False)
    try:
        completed = subprocess.run(
            ["git", "init", "-b", "main", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "git init falló")
        text = f"# {name}\n" + (f"\n{purpose.strip()}\n" if purpose.strip() else "")
        (target / "README.md").write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "add", "README.md"], capture_output=True, check=False)
        subprocess.run(
            ["git", "-C", str(target), "commit", "-m", "Initial commit"],
            capture_output=True,
            check=False,
        )
    except Exception:
        import shutil

        shutil.rmtree(target, ignore_errors=True)
        raise
    _save_selected_project(target)
    return target


def _preset_from_payload(data: dict[str, object]) -> VisualWorkflowPreset:
    kind = str(data.get("kind", ""))
    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list) or any(not isinstance(item, dict) for item in raw_steps):
        raise ValueError("steps debe ser una lista de objetos")
    for field in ('name', 'description'):
        if not isinstance(data.get(field, ''), str):
            raise ValueError(f'{field} debe ser texto')
    return VisualWorkflowPreset(
        kind=kind,
        id=data.get('id'),
        name=data.get('name', ''),
        description=data.get('description', ''),
        steps=tuple(
            VisualWorkflowStep.from_mapping(item)
            for item in raw_steps
            if isinstance(item, dict)
        ),
    )


def _apply_workflow_defaults(args: list[str], project: Path | None) -> list[str]:
    if project is None or not args or args[0] not in {"feature", "fix"}:
        return list(args)
    kind = args[0]
    preset = load_preset(project, kind)
    enabled = [step for step in preset.steps if step.enabled]
    result = list(args)

    if kind == "fix":
        enabled_names = {step.name for step in enabled}
        if "plan" in enabled_names and "--large" not in result:
            result.append("--large")
        if "document" in enabled_names and "--update-memory" not in result:
            result.append("--update-memory")

    has_tool = "--tool" in result
    explicit_tools = {step.tool for step in enabled if step.tool}
    if not has_tool and len(explicit_tools) == 1:
        result.extend(["--tool", next(iter(explicit_tools))])
    return result


def _run_factoria_command(args: list[str], project: Path | None) -> tuple[int, str]:
    assert_ui_command_allowed(args)
    if not args or args[0] not in _ALLOWED_COMMANDS:
        raise ValueError("Comando no permitido desde la web")
    from factoria.entrypoint import main

    argv = _apply_workflow_defaults(args, project)
    if project is not None and "--project" not in argv:
        argv = ["--project", str(project), *argv]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        try:
            code = int(main(argv) or 0)
        except SystemExit as exc:
            code = int(exc.code or 0)
        except Exception as exc:
            code = 1
            print(f"{type(exc).__name__}: {exc}")
    return code, buffer.getvalue()


def _start_async_job(args: list[str], project: Path | None) -> dict[str, object]:
    raise ValueError("Inicia Codex/OpenCode fuera de Factoría; la aplicación no ejecuta agentes")


def _job(job_id: str) -> dict[str, object] | None:
    with _JOBS_LOCK:
        item = _JOBS.get(job_id)
        return dict(item) if item is not None else None


class FactoriaWebHandler(BaseHTTPRequestHandler):
    server_version = "FactoriaWeb/0.3"

    @property
    def token(self) -> str:
        return self.server.factoria_token  # type: ignore[attr-defined]

    def log_message(self, format: str, *args) -> None:
        return

    def _authorized(self) -> bool:
        return self.headers.get("X-Factoria-Token") == self.token

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON inválido")
        return data

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {'/assets/workflows.js', '/assets/templates.js', '/assets/resources.js'}:
            body = files('factoria.web').joinpath(path.rsplit('/', 1)[-1]).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            html = files("factoria.web").joinpath("index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return
        if path == "/api/state":
            self._json(_state())
            return
        if path.startswith("/api/job/"):
            job_id = path.rsplit("/", 1)[-1]
            item = _job(job_id)
            if item is None:
                self._json({"error": "job not found"}, 404)
                return
            self._json({"job": item, "state": _state()})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return
        path = urlparse(self.path).path
        try:
            if path.startswith('/api/resource/') and not 0 <= int(self.headers.get('Content-Length', '0')) <= 16384:
                raise ValueError('Solicitud de recurso demasiado grande o no válida')
            if path.startswith('/api/template/') and not 0 <= int(self.headers.get('Content-Length', '0')) <= 1052672:
                raise ValueError('Tamaño de plantilla no válido o superior al permitido')
            data = self._body()
            if path in {'/api/resource/list','/api/resource/preview','/api/resource/apply'}:
                from factoria.application.resource_lifecycle import resource_inventory, preview_resource, apply_resource, ResourceConflict
                project=_selected_project(UiWorkspaceSettings.load())
                if project is None or data.get('project_path')!=str(project):
                    self._json({'error':'El proyecto cambió; vuelve a revisar impacto'},409)
                    return
                try:
                    if path.endswith('/list'):result=resource_inventory(project)
                    elif path.endswith('/preview'):result=preview_resource(project,data.get('request'))
                    else:result=apply_resource(project,data.get('request'),token=data.get('token'),confirmed=data.get('confirmed') is True)
                    self._json({'ok':True,**result})
                except ResourceConflict as exc:self._json({'error':str(exc)},409)
                return
            if path in {'/api/template/export', '/api/template/preview', '/api/template/apply'}:
                from factoria.application.project_templates import export_template, preview_template, apply_template, TemplateConflict
                project = _selected_project(UiWorkspaceSettings.load())
                if project is None or data.get('project_path') != str(project):
                    self._json({'error': 'El proyecto seleccionado cambió; vuelve a previsualizar'}, 409)
                    return
                try:
                    if path.endswith('/export'):
                        result = {'template': export_template(project, data.get('name', ''))}
                    elif path.endswith('/preview'):
                        result = preview_template(project, data.get('template'))
                    else:
                        result = apply_template(project, data.get('template'), expected_token=data.get('token'), confirmed=data.get('confirmed') is True)
                    self._json({'ok': True, **result})
                except TemplateConflict as exc:
                    self._json({'error': str(exc)}, 409)
                return
            if path == "/api/projects/root":
                target = _set_projects_root(str(data.get("path", "")))
                self._json({"ok": True, "path": str(target), "state": _state()})
                return
            if path == "/api/project/select":
                target = Path(str(data.get("path", ""))).expanduser().resolve()
                _save_selected_project(target)
                self._json({"ok": True, "state": _state()})
                return
            if path == "/api/project/create":
                target = _create_project(str(data.get("name", "")), str(data.get("purpose", "")))
                self._json({"ok": True, "path": str(target), "state": _state()})
                return
            if path == "/api/agent/default":
                written = _set_default_tool(str(data.get("tool", "")))
                self._json({"ok": True, "config": str(written), "state": _state()})
                return
            if path == "/api/agent/path":
                configured = _set_agent_path(str(data.get("tool", "")), str(data.get("path", "")))
                self._json({"ok": True, "path": str(configured), "state": _state()})
                return
            if path in {"/api/workflow/save", "/api/workflow/create"}:
                settings = UiWorkspaceSettings.load()
                project = _selected_project(settings)
                if project is None:
                    raise ValueError("Selecciona primero un proyecto")
                if data.get('project_path') != str(project):
                    raise WorkflowCatalogConflict('El proyecto del borrador ya no está seleccionado; vuelve a cargar')
                if not isinstance(data.get('revision'), str):
                    raise ValueError('Falta la versión del catálogo; vuelve a cargar el flujo')
                preset = _preset_from_payload(data)
                saved = save_preset(project, preset, expected_revision=data['revision'], create=path.endswith('/create'))
                self._json({"ok": True, "path": str(saved), "state": _state()})
                return
            if path == "/api/job/start":
                raw = data.get("args", [])
                if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                    raise ValueError("args debe ser una lista de strings")
                settings = UiWorkspaceSettings.load()
                job = _start_async_job(list(raw), _selected_project(settings))
                self._json({"ok": True, "job": job, "state": _state()}, 202)
                return
            if path == "/api/command":
                raw = data.get("args", [])
                if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                    raise ValueError("args debe ser una lista de strings")
                settings = UiWorkspaceSettings.load()
                code, output = _run_factoria_command(list(raw), _selected_project(settings))
                self._json({"ok": code == 0, "code": code, "output": output, "state": _state()})
                return
            raise ValueError("Acción no soportada")
        except WorkflowCatalogConflict as exc:
            self._json({"ok": False, "error": str(exc)}, 409)
        except Exception as exc:
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)


class FactoriaHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    factoria_token: str


def run_web_ui(*, open_browser: bool = True) -> int:
    _apply_agent_paths()
    token = secrets.token_urlsafe(24)
    server = FactoriaHTTPServer((_HOST, 0), FactoriaWebHandler)
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
