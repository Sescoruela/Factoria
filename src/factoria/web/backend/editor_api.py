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
        "/api/project/memory-graph",
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
            if "project_path" in data and data["project_path"] != str(project):
                self._json({"error": "El proyecto seleccionado cambió. Vuelve a revisarlo."}, 409)
                return
            service = ProjectIntegration(project)
            confirmed = data.get("confirmed") is True
            revision = data.get("revision")
            if "project_path" in data and confirmed and not isinstance(revision, str):
                raise ValueError("Revisa los archivos antes de aplicar la preparación.")
            plan = (
                service.apply(confirmed=True, expected_revision=revision)
                if confirmed
                else service.plan()
            )
            self._json(
                {
                    "ok": True,
                    "applied": confirmed,
                    "revision": plan.revision,
                    "changed": list(plan.changed),
                    "conflicts": list(plan.conflicts),
                    "state": self._editor_state(),
                }
            )
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        return
    if path == "/api/project/memory-graph":
        try:
            data = self._body()
            project = self._active_project()
            if project is None or data.get("project_path") != str(project):
                self._json({"error": "El proyecto seleccionado cambió. Vuelve a abrirlo."}, 409)
                return
            from factoria.application.projects.memory_graph import project_memory_graph

            if data.get("action") == "build":
                result = project_memory_graph(project, rebuild=True)
            elif data.get("action") == "recall" and isinstance(data.get("query"), str):
                result = project_memory_graph(project, query=data["query"])
            else:
                raise ValueError("Indica qué quieres buscar en la memoria.")
            self._json(result)
        except FileNotFoundError as exc:
            message = str(exc)
            if message.startswith("Grafo sin generar."):
                message = "Primero pulsa Generar índice."
            self._json({"error": message}, 400)
        except Exception as exc:
            self._json({"error": str(exc)}, 400)
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
