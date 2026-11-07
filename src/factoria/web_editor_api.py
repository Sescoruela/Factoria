"""Shared authenticated editor endpoints; independent of the selected shell."""

from __future__ import annotations

from urllib.parse import urlparse

from factoria.application.agent_profiles import (
    AgentCatalogConflict,
    AgentRoleProfile,
    save_agent_profile,
)
from factoria.application.project_integration import ProjectIntegration
from factoria.application.skill_catalog import SkillCatalogConflict, SkillDefinition, save_skill
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import _selected_project, _editor_state as _extended_state


def handle_editor_post(self) -> bool:
    path = urlparse(self.path).path
    if path in {"/api/skill/create", "/api/skill/save"}:
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return True
        try:
            data = self._body()
            project = _selected_project(UiWorkspaceSettings.load())
            if project is None:
                raise ValueError("Selecciona primero un proyecto")
            if data.get("project_path") != str(project):
                raise SkillCatalogConflict("El proyecto del borrador cambió; vuelve a cargarlo")
            if not isinstance(data.get("revision"), str):
                raise ValueError("Falta la versión del catálogo; vuelve a cargar las skills")
            saved = save_skill(
                project,
                SkillDefinition.from_mapping(data),
                expected_revision=data["revision"],
                create=path.endswith("/create"),
            )
            self._json({"ok": True, "path": str(saved), "state": _extended_state()})
        except SkillCatalogConflict as exc:
            self._json({"ok": False, "error": str(exc)}, 409)
        except (ValueError, OSError) as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        return True
    if path == "/api/project/prepare":
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return True
        try:
            data = self._body()
            project = _selected_project(UiWorkspaceSettings.load())
            if project is None:
                raise ValueError("Selecciona primero un proyecto")
            service = ProjectIntegration(project)
            confirmed = data.get("confirmed") is True
            plan = service.apply(confirmed=True) if confirmed else service.plan()
            self._json(
                {
                    "ok": True,
                    "applied": confirmed,
                    "changed": list(plan.changed),
                    "conflicts": list(plan.conflicts),
                    "state": _extended_state(),
                }
            )
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        return True
    if path in {"/api/agent-role/save", "/api/agent-role/create"}:
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return True
        try:
            data = self._body()
            project = _selected_project(UiWorkspaceSettings.load())
            if project is None:
                raise ValueError("Selecciona primero un proyecto")
            if data.get("project_path") != str(project):
                raise AgentCatalogConflict(
                    "El proyecto seleccionado cambió; vuelve a cargar el editor"
                )
            if not isinstance(data.get("revision"), str):
                raise ValueError("Falta la versión del catálogo; vuelve a cargar el editor")
            profile = AgentRoleProfile.from_mapping(data)
            saved = save_agent_profile(
                project,
                profile,
                expected_revision=data["revision"],
                mode="create" if path.endswith("/create") else "update",
            )
            self._json({"ok": True, "path": str(saved), "state": _extended_state()})
        except AgentCatalogConflict as exc:
            self._json({"ok": False, "error": str(exc)}, 409)
        except Exception as exc:
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
        return True
    return False
