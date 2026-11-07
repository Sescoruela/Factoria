"""Portable closed bundles of project resources, with conservative preview/import."""

from __future__ import annotations

from factoria.storage import staged_bytes

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from factoria.application import agent_profiles as agents
from factoria.application import skill_catalog as skills
from factoria.application import workflow_presets as workflows
from factoria.project_paths import project_path
from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.application.resource_support import (
    json_bytes as _json,
    scan_secrets as _scan,
    catalog_locks as _locks,
    catalog_revision as _revision,
    skill_bytes as _skill_bytes,
    read_catalog as _raw,
)

MAX_TEMPLATE_BYTES = 1024 * 1024


class TemplateConflict(ValueError):
    pass


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("Formato de plantilla no válido o campos no portables")


def validate_template(data: dict) -> dict:
    _fields(
        data,
        ("schema_version", "name", "skills", "agents", "workflows"),
        ("schema_version", "name", "skills", "agents", "workflows"),
    )
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Versión de plantilla no soportada")
    if not isinstance(data["name"], str) or not data["name"].strip() or len(data["name"]) > 120:
        raise ValueError("La plantilla necesita un nombre de hasta 120 caracteres")
    if len(_json(data)) > MAX_TEMPLATE_BYTES:
        raise ValueError("La plantilla supera 1 MiB")
    _scan(data)
    if not all(isinstance(data[k], list) for k in ("skills", "agents")) or not isinstance(
        data["workflows"], dict
    ):
        raise ValueError("Catálogos de plantilla no válidos")
    skill_items, agent_items, preset_items = [], [], {}
    for raw in data["skills"]:
        _fields(raw, ("id", "name", "description", "content"), ("id", "name", "content"))
        skill_items.append(skills.validate_skill(skills.SkillDefinition.from_mapping(raw)))
    for raw in data["agents"]:
        _fields(raw, agents.AgentRoleProfile.__dataclass_fields__, ("role", "profile"))
        agent_items.append(agents.validate_agent_profile(agents.AgentRoleProfile.from_mapping(raw)))
    for items, key in ((skill_items, "id"), (agent_items, "role")):
        names = [getattr(item, key).casefold() for item in items]
        if len(set(names)) != len(names):
            raise ValueError("Identificadores duplicados en la plantilla")
    available = {item.path for item in skill_items}
    if any(path not in available for item in agent_items for path in item.skills):
        raise ValueError("Todas las skills referenciadas deben pertenecer al catálogo exportado")
    for identifier, raw in data["workflows"].items():
        _fields(raw, ("kind", "id", "name", "description", "steps"), ("kind", "steps"))
        if not isinstance(raw["steps"], list):
            raise ValueError("Etapas no válidas")
        for step in raw["steps"]:
            _fields(step, workflows.VisualWorkflowStep.__dataclass_fields__, ("name", "role"))
        builtin = identifier in ("fix", "feature")
        if raw.get("id", identifier) != identifier or (builtin and raw["kind"] != identifier):
            raise ValueError("Identificador/tipo base incoherente")
        preset = workflows.VisualWorkflowPreset(
            raw["kind"],
            tuple(workflows.VisualWorkflowStep.from_mapping(s) for s in raw["steps"]),
            id=None if builtin else identifier,
            name=raw.get("name", ""),
            description=raw.get("description", ""),
        )
        preset_items[identifier] = workflows.validate_assignments(preset, agent_items)
    if len({key.casefold() for key in preset_items}) != len(preset_items):
        raise ValueError("Workflows duplicados")
    return {
        "schema_version": 1,
        "name": data["name"].strip(),
        "skills": [asdict(item) for item in skill_items],
        "agents": [item.to_mapping() for item in agent_items],
        "workflows": {key: item.to_mapping() for key, item in preset_items.items()},
    }


def read_template(path: Path) -> dict:
    if path.is_symlink() or path.stat().st_size > MAX_TEMPLATE_BYTES:
        raise ValueError("Archivo de plantilla no válido o demasiado grande")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Claves JSON duplicadas")
            result[key] = value
        return result

    return validate_template(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique))


def export_template(root: Path, name: str) -> dict:
    root = root.resolve()
    with _locks():
        before = _revision(root)
        catalog, _, _ = skills.skill_catalog_snapshot(root)
        payload = validate_template(
            {
                "schema_version": 1,
                "name": name,
                "skills": [asdict(item) for item in catalog],
                "agents": [item.to_mapping() for item in agents.load_agent_profiles(root)],
                "workflows": {
                    key: item.to_mapping() for key, item in workflows.load_catalog(root).items()
                },
            }
        )
        if before != _revision(root):
            raise TemplateConflict(
                "La configuración cambió durante la exportación; vuelve a cargar"
            )
        return payload


def _plan(root: Path, payload: dict):
    root = root.resolve()
    data = validate_template(payload)
    from factoria.application.resource_archive import assert_not_archived

    for kind, identifiers in (
        ("skill", [s["id"] for s in data["skills"]]),
        ("agent", [a["role"] for a in data["agents"]]),
        ("workflow", data["workflows"]),
    ):
        for identifier in identifiers:
            assert_not_archived(root, kind, identifier)
    before = _revision(root)
    current_skills, _, foreign = skills.skill_catalog_snapshot(root)
    current_agents = {item.role: item.to_mapping() for item in agents.load_agent_profiles(root)}
    current_flows = {key: item.to_mapping() for key, item in workflows.load_catalog(root).items()}
    merged_agents = _raw(root, ".factoria/agents.json", ".factoria/ui-agents.json")
    merged_flows = _raw(root, ".factoria/workflows.json", ".factoria/ui-workflows.json")
    create, reuse, conflicts, writes = [], [], [], {}
    existing = {item.id: asdict(item) for item in current_skills}
    occupied = {
        item.casefold(): item for item in [*(s.id + ".md" for s in current_skills), *foreign]
    }
    for raw in data["skills"]:
        identifier = raw["id"]
        relative = f".factoria/skills/{identifier}.md"
        if existing.get(identifier) == raw:
            reuse.append(relative)
        elif (identifier + ".md").casefold() in occupied:
            conflicts.append(relative)
        else:
            project_path(root, relative)
            create.append(relative)
            writes[relative] = _skill_bytes(raw)
    for kind, incoming, current, merged, relative in (
        (
            "agent",
            {a["role"]: a for a in data["agents"]},
            current_agents,
            merged_agents,
            ".factoria/agents.json",
        ),
        ("workflow", data["workflows"], current_flows, merged_flows, ".factoria/workflows.json"),
    ):
        changed = False
        for identifier, raw in incoming.items():
            label = f"{kind}:{identifier}"
            if current.get(identifier) == raw:
                reuse.append(label)
            elif identifier in merged or (
                identifier in current
                and identifier not in ("fix", "feature")
                and kind == "workflow"
            ):
                conflicts.append(label)
            else:
                merged[identifier] = raw
                create.append(label)
                changed = True
        if changed:
            writes[relative] = _json(merged)
    if before != _revision(root):
        raise TemplateConflict("La configuración cambió durante el preview; vuelve a cargar")
    token = hashlib.sha256(_json([before, data])).hexdigest()
    return {
        "project_path": str(root),
        "name": data["name"],
        "token": token,
        "create": create,
        "reuse": reuse,
        "conflicts": conflicts,
    }, writes


def preview_template(root: Path, data: dict) -> dict:
    with _locks():
        return _plan(root, data)[0]


def apply_template(root: Path, data: dict, *, expected_token: str, confirmed: bool) -> dict:
    from factoria.application.config_schema import assert_config_writable

    if root is not None:
        assert_config_writable(root)
    if not confirmed:
        raise PermissionError("Revisa el preview y confirma la importación")
    root = root.resolve()
    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(root))
    with _locks():
        assert_config_writable(root)
        plan, writes = _plan(root, data)
        if not isinstance(expected_token, str) or expected_token != plan["token"]:
            raise TemplateConflict("El proyecto o la plantilla cambió; vuelve a previsualizar")
        if plan["conflicts"]:
            raise TemplateConflict("Hay conflictos; no se sobrescribe ningún recurso")
        if not writes:
            return {**plan, "applied": True, "backup": None}
        # Local recovery record before any catalog write. Not exported.
        git = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-path", "factoria/template-imports"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        backup = Path(git)
        if not backup.is_absolute():
            backup = root / backup
        backup = backup / str(uuid.uuid4())
        if any(path.is_symlink() for path in (backup, *backup.parents)):
            raise ValueError("No se permiten symlinks en la copia local de recuperación")
        backup.mkdir(parents=True)
        originals = {
            name: project_path(root, name).read_bytes()
            if project_path(root, name).exists()
            else None
            for name in writes
        }
        for index, (name, content) in enumerate(originals.items()):
            if content is not None:
                (backup / f"{index}.bak").write_bytes(content)
        journal = {
            "state": "pending",
            "files": [
                {"path": name, "original": f"{index}.bak" if content is not None else None}
                for index, (name, content) in enumerate(originals.items())
            ],
        }
        (backup / "journal.json").write_bytes(_json(journal))
        completed = []
        try:
            if _plan(root, data)[0]["token"] != expected_token:
                raise TemplateConflict("Cambio externo antes de aplicar; vuelve a previsualizar")
            for name, content in writes.items():
                target = project_path(root, name)
                if (target.read_bytes() if target.exists() else None) != originals[name]:
                    raise TemplateConflict("Cambio externo durante importación")
                with staged_bytes(target, content) as temporary:
                    project_path(root, name)
                    if originals[name] is None:
                        os.link(temporary, target)
                    else:
                        os.replace(temporary, target)
                    completed.append(name)
            journal["state"] = "applied"
        except Exception as error:
            journal["state"] = "failed"
            journal["recovery_needed"] = []
            for name in reversed(completed):
                try:
                    target = project_path(root, name)
                    # Never undo an external edit made after our write.
                    if not target.exists() or target.read_bytes() != writes[name]:
                        journal["recovery_needed"].append(name)
                        continue
                    if originals[name] is None:
                        target.unlink()
                    else:
                        with staged_bytes(target, originals[name]) as temporary:
                            os.replace(temporary, target)
                except Exception:
                    journal["recovery_needed"].append(name)
            if journal["recovery_needed"]:
                raise RuntimeError(
                    f"Importación interrumpida; se conservaron cambios externos o una restauración falló. Revisar copia local: {backup}"
                ) from error
            raise
        finally:
            (backup / "journal.json").write_bytes(_json(journal))
        return {
            **plan,
            "applied": True,
            "backup": str(backup),
            "next": "Revisar el diff y preparar ambas herramientas; no se ha cambiado memoria ni política.",
        }
