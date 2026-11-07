"""HTTP transport for project resources, templates, diagnostics and recovery.

Authentication stays at the server boundary; each feature retains its project and
revision checks. No shell-specific handler imports or provider startup.
"""

from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import _selected_project

PROJECT_RESOURCE_ROUTES = frozenset(
    {
        "/api/config/status",
        "/api/config/preview",
        "/api/config/apply",
        "/api/project/relations",
        "/api/resource/list",
        "/api/resource/preview",
        "/api/resource/apply",
        "/api/template/export",
        "/api/template/preview",
        "/api/template/apply",
    }
)


def handle_project_post(self, path: str) -> None:
    if path in {"/api/config/status", "/api/config/preview", "/api/config/apply"}:
        if not 0 <= int(self.headers.get("Content-Length", "0")) <= 16384:
            raise ValueError("Solicitud demasiado grande")
        data = self._body()
        project = _selected_project(UiWorkspaceSettings.load())
        if project is None or data.get("project_path") != str(project):
            self._json({"error": "El proyecto cambió; volver a revisar"}, 409)
            return
        from factoria.application.config_recovery import (
            config_status,
            preview_config,
            apply_config,
        )

        result = (
            config_status(project)
            if path.endswith("/status")
            else apply_config(
                project,
                data.get("action"),
                identifier=data.get("backup_id"),
                token=data.get("token"),
                confirmed=data.get("confirmed") is True,
            )
            if path.endswith("/apply")
            else preview_config(project, data.get("action"), data.get("backup_id"))
        )
        self._json({"ok": True, **result})
        return
    if path == "/api/project/relations":
        if not 0 <= int(self.headers.get("Content-Length", "0")) <= 16384:
            raise ValueError("Solicitud demasiado grande")
        data = self._body()
        project = _selected_project(UiWorkspaceSettings.load())
        if project is None or data.get("project_path") != str(project):
            self._json({"error": "El proyecto cambió; vuelve a cargar las relaciones"}, 409)
            return
        from factoria.application.project_relations import project_relations

        self._json({"ok": True, **project_relations(project)})
        return
    if (
        path.startswith("/api/resource/")
        and not 0 <= int(self.headers.get("Content-Length", "0")) <= 16384
    ):
        raise ValueError("Solicitud de recurso demasiado grande o no válida")
    if (
        path.startswith("/api/template/")
        and not 0 <= int(self.headers.get("Content-Length", "0")) <= 1052672
    ):
        raise ValueError("Tamaño de plantilla no válido o superior al permitido")
    data = self._body()
    if path in {"/api/resource/list", "/api/resource/preview", "/api/resource/apply"}:
        from factoria.application.resource_lifecycle import (
            resource_inventory,
            preview_resource,
            apply_resource,
            ResourceConflict,
        )

        project = _selected_project(UiWorkspaceSettings.load())
        if project is None or data.get("project_path") != str(project):
            self._json({"error": "El proyecto cambió; vuelve a revisar impacto"}, 409)
            return
        try:
            if path.endswith("/list"):
                result = resource_inventory(project)
            elif path.endswith("/preview"):
                result = preview_resource(project, data.get("request"))
            else:
                result = apply_resource(
                    project,
                    data.get("request"),
                    token=data.get("token"),
                    confirmed=data.get("confirmed") is True,
                )
            self._json({"ok": True, **result})
        except ResourceConflict as exc:
            self._json({"error": str(exc)}, 409)
        return
    if path in {"/api/template/export", "/api/template/preview", "/api/template/apply"}:
        from factoria.application.project_templates import (
            export_template,
            preview_template,
            apply_template,
            TemplateConflict,
        )

        project = _selected_project(UiWorkspaceSettings.load())
        if project is None or data.get("project_path") != str(project):
            self._json({"error": "El proyecto seleccionado cambió; vuelve a previsualizar"}, 409)
            return
        try:
            if path.endswith("/export"):
                result = {"template": export_template(project, data.get("name", ""))}
            elif path.endswith("/preview"):
                result = preview_template(project, data.get("template"))
            else:
                result = apply_template(
                    project,
                    data.get("template"),
                    expected_token=data.get("token"),
                    confirmed=data.get("confirmed") is True,
                )
            self._json({"ok": True, **result})
        except TemplateConflict as exc:
            self._json({"error": str(exc)}, 409)
        return
