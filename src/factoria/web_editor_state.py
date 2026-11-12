"""Shared editor-state composition for both HTTP shells."""

from factoria.application.agent_profiles import agent_catalog_snapshot
from factoria.application.engineering_templates import (
    API_MIGRATION,
    INTEGRATION_PLANNER,
    PRODUCTION_DIAGNOSTICS,
    SQL_DIAGNOSTICS,
)
from factoria.application.product_design import PRODUCT_DESIGNER, SKILL_TEMPLATES
from factoria.application.skill_catalog import skill_catalog_snapshot
from factoria.application.project_integration import ProjectIntegration
from factoria.application.visual_agents import visual_agent_templates


def enrich_editor_state(payload: dict, project) -> dict[str, object]:
    platforms = list(payload.get("agents", []))
    payload["platforms"] = platforms
    payload["agent_templates"] = [
        item.to_mapping()
        for item in (*visual_agent_templates(), PRODUCT_DESIGNER, INTEGRATION_PLANNER)
    ]
    payload["skill_templates"] = [
        item.to_mapping()
        for item in (*SKILL_TEMPLATES, API_MIGRATION, SQL_DIAGNOSTICS, PRODUCTION_DIAGNOSTICS)
    ]
    try:
        skills, revision, foreign = skill_catalog_snapshot(project)
        payload["skills"] = [skill.to_mapping() for skill in skills]
        payload["skill_catalog_revision"] = revision
        payload["unmanaged_skill_files"] = list(foreign)
    except (ValueError, OSError) as exc:
        payload["skills"] = []
        payload["skill_configuration_error"] = str(exc)
    try:
        agents, revision = agent_catalog_snapshot(project)
        payload["agent_roles"] = [item.to_mapping() for item in agents]
        payload["agent_catalog_revision"] = revision
    except (ValueError, OSError) as exc:
        payload["agent_roles"] = []
        payload["agent_configuration_error"] = str(exc)
    if project is not None:
        try:
            payload["integration"] = ProjectIntegration(project).check()
        except (ValueError, OSError) as exc:
            payload["integration"] = {"ready": False, "error": str(exc)}
    return payload
