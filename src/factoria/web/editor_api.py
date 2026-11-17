"""Shared authenticated editor endpoints; independent of the selected shell."""

from __future__ import annotations

from factoria.application.projects.agent_profiles import (
    AgentCatalogConflict,
    AgentRoleProfile,
    save_agent_profile,
)
from factoria.application.projects.project_integration import ProjectIntegration
from factoria.application.projects.skill_catalog import (
    SkillCatalogConflict,
    SkillDefinition,
    save_skill,
)


EDITOR_ROUTES = frozenset(
    {
        "/api/skill/create",
        "/api/skill/save",
        "/api/agent-role/create",
        "/api/agent-role/save",
        "/api/project/prepare",
    }
)


def handle_editor_post(self, path: str) -> None:
    if path in {"/api/skill/create", "/api/skill/save"}:
        try:
            data = self._body()
            project = self._active_project()
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
            self._json({"ok": True, "path": str(saved), "state": self._editor_state()})
        except SkillCatalogConflict as exc:
            self._json({"ok": False, "error": str(exc)}, 409)
        except (ValueError, OSError) as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        return
    if path == "/api/project/prepare":
        try:
            data = self._body()
            project = self._active_project()
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
                    "state": self._editor_state(),
                }
            )
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        return
    if path in {"/api/agent-role/save", "/api/agent-role/create"}:
        try:
            data = self._body()
            project = self._active_project()
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
            self._json({"ok": True, "path": str(saved), "state": self._editor_state()})
        except AgentCatalogConflict as exc:
            self._json({"ok": False, "error": str(exc)}, 409)
        except Exception as exc:
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
