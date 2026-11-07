"""Duplicate/archive/restore resources without rewriting their consumers or snapshots."""

from __future__ import annotations

from factoria.storage import atomic_write_bytes

from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import tempfile
import uuid

from factoria.application import (
    agent_profiles as agents,
    skill_catalog as skills,
    workflow_presets as workflows,
)
from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.project_paths import project_path
from factoria.application.resource_support import (
    json_bytes as _json,
    catalog_locks as _locks,
    read_catalog as _raw,
    catalog_revision as _revision,
    scan_secrets as _scan,
    skill_bytes as _skill_bytes,
)
from factoria.application.resource_archive import DIRECTORY, archive_records, assert_not_archived


class ResourceConflict(ValueError):
    pass


def _catalogs(root):
    return {
        "skill": {s.id: s for s in skills.skill_catalog_snapshot(root)[0]},
        "agent": {a.role: a for a in agents.load_agent_profiles(root)},
        "workflow": workflows.load_catalog(root),
    }


def resource_inventory(root: Path) -> dict:
    with _locks():
        before = _revision(root)
        catalog = _catalogs(root)
        result = {
            "active": [
                {"kind": kind, "id": identifier, "name": getattr(item, "name", "") or identifier}
                for kind, items in catalog.items()
                for identifier, item in items.items()
            ],
            "history": [
                {
                    "archive_id": key,
                    **{
                        field: record.get(field)
                        for field in (
                            "kind",
                            "id",
                            "status",
                            "action",
                            "created_at",
                            "restored_at",
                            "source_id",
                        )
                    },
                }
                for key, record in archive_records(root).items()
            ],
        }
        if _revision(root) != before:
            raise ResourceConflict("El catálogo cambió durante la lectura")
        return result


def _path(kind, identifier):
    return (
        f".factoria/skills/{identifier}.md"
        if kind == "skill"
        else f".factoria/{'agents' if kind == 'agent' else 'workflows'}.json"
    )


def _snapshot_usage(root, kind, identifier):
    result = []
    for path in project_path(root, ".factoria/work").glob("*/native.json"):
        # Read bounded, project-owned snapshots without following symlinks.
        target = project_path(root, path.relative_to(root).as_posix())
        if target.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Snapshot demasiado grande para revisar impacto")
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("definition", {}), dict):
            raise ValueError("Snapshot no válida para revisar impacto")
        profiles = data.get("definition", {}).get("agents", [])
        if not isinstance(profiles, list) or any(
            not isinstance(a, dict) or not isinstance(a.get("skills", []), list) for a in profiles
        ):
            raise ValueError("Catálogo de snapshot no válido para revisar impacto")
        if (
            (kind == "workflow" and data.get("workflow_id", data.get("kind")) == identifier)
            or (kind == "agent" and any(a.get("role") == identifier for a in profiles))
            or (
                kind == "skill"
                and any(
                    any(
                        project_path(root, path)
                        == project_path(root, f".factoria/skills/{identifier}.md")
                        for path in a.get("skills", [])
                    )
                    for a in profiles
                )
            )
        ):
            result.append(path.parent.name)
    return result


def _record_payload(root, kind, identifier, item):
    canonical = asdict(item) if kind == "skill" else item.to_mapping()
    if kind == "skill":
        raw = project_path(root, item.path).read_bytes().decode("utf-8")
    else:
        raw = _raw(
            root,
            _path(kind, identifier),
            f".factoria/ui-{'agents' if kind == 'agent' else 'workflows'}.json",
        ).get(identifier)
        if raw is None:
            raw = canonical
    payload = {"resource": canonical, "raw": raw}
    _scan(payload)
    if len(_json(payload)) > 2 * 1024 * 1024 - 4096:
        raise ValueError("El recurso supera el tamaño permitido para archivar")
    return payload


def _sources(root):
    names = [
        ".factoria/agents.json",
        ".factoria/ui-agents.json",
        ".factoria/workflows.json",
        ".factoria/ui-workflows.json",
    ]
    names += [p.relative_to(root).as_posix() for p in skills._files(root)]
    return {
        name: project_path(root, name).read_bytes() if project_path(root, name).exists() else None
        for name in names
    }


def _validate_restored(root, kind, identifier, record):
    resource, raw = record["resource"], record["raw"]
    _scan(resource)
    _scan(raw)
    if kind == "skill":
        item = skills.validate_skill(skills.SkillDefinition.from_mapping(resource))
        if item.id != identifier or not isinstance(raw, str):
            raise ValueError("Identidad de skill archivada no válida")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / (identifier + ".md")
            path.write_bytes(raw.encode("utf-8"))
            if skills._decode(path) != item:
                raise ValueError("El contenido archivado no coincide con su definición")
        return raw.encode("utf-8")
    if not isinstance(raw, dict):
        raise ValueError("Definición archivada no válida")
    if kind == "agent":
        item = agents.validate_agent_profile(
            agents.AgentRoleProfile.from_mapping({**raw, "role": identifier})
        )
        expected = agents.validate_agent_profile(agents.AgentRoleProfile.from_mapping(resource))
        if item != expected or item.role != identifier:
            raise ValueError("Identidad de agente archivado no válida")
        for path in item.skills:
            if not project_path(root, path).is_file():
                raise ValueError(f"Restaurar primero la skill referenciada: {path}")
    else:
        if (
            not isinstance(raw.get("kind"), str)
            or not isinstance(raw.get("steps"), list)
            or any(not isinstance(s, dict) for s in raw["steps"])
        ):
            raise ValueError("Etapas archivadas no válidas")
        item = workflows.validate_assignments(
            workflows.VisualWorkflowPreset(
                raw["kind"],
                tuple(workflows.VisualWorkflowStep.from_mapping(s) for s in raw["steps"]),
                id=identifier,
                name=raw.get("name", ""),
                description=raw.get("description", ""),
            ),
            agents.load_agent_profiles(root),
        )
        if _json(item.to_mapping()) != _json(resource):
            raise ValueError("El workflow archivado no coincide con su definición")
    return raw


def _plan(root: Path, request: dict):
    root = root.resolve()
    if (
        not isinstance(request, dict)
        or set(request) - {"action", "kind", "id", "new_id", "name", "archive_id"}
        or request.get("action") not in ("duplicate", "archive", "restore")
        or request.get("kind") not in ("skill", "agent", "workflow")
    ):
        raise ValueError("Operación de recurso no válida")
    before = _revision(root)
    source_files = _sources(root)
    catalog = _catalogs(root)
    records = archive_records(root)
    kind, action = request["kind"], request["action"]
    identifier = request.get("id")
    record = None
    record_id = None
    blockers = []
    snapshots = []
    if action == "restore":
        record_id = request.get("archive_id")
        if not isinstance(record_id, str) or not re.fullmatch("[0-9a-f]{32}", record_id):
            raise ValueError("Registro no válido")
        record = records.get(record_id)
        if not record or record["status"] != "archived" or record["kind"] != kind:
            raise ValueError("El recurso no está disponible para restaurar")
        identifier = record["id"]
        if identifier in catalog[kind] or (
            kind == "skill"
            and any(p.name.casefold() == identifier.casefold() + ".md" for p in skills._files(root))
        ):
            blockers.append("El identificador o la ruta ya existe; no se sobrescribe")
        for other_id, other in records.items():
            if (
                other_id != record_id
                and other["kind"] == kind
                and other["id"] == identifier
                and other["status"] in ("archived", "pending")
            ):
                blockers.append("Otro registro reserva este identificador")
        payload = _validate_restored(root, kind, identifier, record)
    else:
        if not isinstance(identifier, str) or identifier not in catalog[kind]:
            raise ValueError("Selecciona un recurso activo")
        item = catalog[kind][identifier]
        if action == "archive":
            if (
                kind == "agent" and identifier in {a.role for a in agents.default_agent_profiles()}
            ) or (kind == "workflow" and identifier in ("fix", "feature")):
                blockers.append("Los recursos básicos no se archivan; duplicar para personalizar")
            if kind == "skill":
                blockers.extend(
                    "agent:" + a.role
                    for a in catalog["agent"].values()
                    if any(
                        project_path(root, path) == project_path(root, item.path)
                        for path in a.skills
                    )
                )
            if kind == "agent":
                blockers.extend(
                    "workflow:" + w.identifier
                    for w in catalog["workflow"].values()
                    if any((s.agent_id or s.role) == identifier for s in w.steps)
                )
            snapshots = _snapshot_usage(root, kind, identifier)
            payload = _record_payload(root, kind, identifier, item)
            _scan(payload)
        else:
            new_id = request.get("new_id")
            name = request.get("name")
            if not isinstance(new_id, str) or (name is not None and not isinstance(name, str)):
                raise ValueError("Escribe un identificador nuevo y un nombre de texto")
            title = (
                name
                if name is not None
                else ((getattr(item, "name", "") or identifier) + " (copia)")[:120]
            )
            if kind == "skill":
                copy = skills.validate_skill(replace(item, id=new_id, name=title))
                payload = _skill_bytes(asdict(copy))
                if any(p.name.casefold() == new_id.casefold() + ".md" for p in skills._files(root)):
                    blockers.append("La ruta de skill ya existe")
            elif kind == "agent":
                copy = agents.validate_agent_profile(
                    replace(item, role=new_id, base_role=item.base_role or item.role, name=title)
                )
                for path in copy.skills:
                    if not project_path(root, path).is_file():
                        raise ValueError("Skill referenciada no disponible")
                payload = copy.to_mapping()
            else:
                copy = workflows.validate_assignments(
                    replace(item, id=new_id, name=title), catalog["agent"].values()
                )
                payload = copy.to_mapping()
            if new_id in catalog[kind]:
                blockers.append("El identificador ya existe")
            assert_not_archived(root, kind, new_id)
            _scan(asdict(copy))
            identifier = new_id
    relative = _path(kind, identifier)
    if kind == "skill":
        content = None if action == "archive" else payload
    else:
        merged = _raw(
            root, relative, f".factoria/ui-{'agents' if kind == 'agent' else 'workflows'}.json"
        )
        if action == "archive":
            merged.pop(identifier, None)
        else:
            merged[identifier] = payload
        content = _json(merged)
    original = (
        project_path(root, relative).read_bytes() if project_path(root, relative).exists() else None
    )
    previous_record = (
        project_path(root, f"{DIRECTORY}/{record_id}.json").read_bytes() if record_id else None
    )
    if before != _revision(root) or source_files != _sources(root):
        raise ResourceConflict("El proyecto cambió; volver a revisar impacto")
    token = hashlib.sha256(_json([before, request, snapshots])).hexdigest()
    return (
        {
            "project_path": str(root),
            "action": action,
            "kind": kind,
            "id": identifier,
            "blockers": blockers,
            "snapshots_preserved": snapshots,
            "token": token,
        },
        relative,
        content,
        record_id,
        record,
        payload,
        original,
        previous_record,
        source_files,
    )


def preview_resource(root: Path, request: dict) -> dict:
    with _locks():
        return _plan(root, request)[0]


def _write(path: Path, content: bytes, *, create=False):
    atomic_write_bytes(path, content, create=create)


def apply_resource(root: Path, request: dict, *, token: str, confirmed: bool) -> dict:
    from factoria.application.config_schema import assert_config_writable

    if root is not None:
        assert_config_writable(root)
    if not confirmed:
        raise PermissionError("Revisar impacto y confirmar antes de aplicar")
    root = root.resolve()
    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(root))
    with _locks():
        assert_config_writable(root)
        (
            plan,
            relative,
            content,
            record_id,
            record,
            payload,
            original,
            previous_record,
            source_files,
        ) = _plan(root, request)
        if token != plan["token"]:
            raise ResourceConflict("El proyecto o la operación cambió; volver a previsualizar")
        if plan["blockers"]:
            raise ResourceConflict("Hay referencias o conflictos: no se aplica la operación")
        target = project_path(root, relative)
        action = request["action"]
        now = datetime.now(UTC).isoformat()
        if record is None:
            record_id = uuid.uuid4().hex
            source = _catalogs(root)[request["kind"]][request["id"]]
            record = {
                "schema_version": 1,
                "kind": request["kind"],
                "id": plan["id"],
                "action": action,
                "source_id": request["id"],
                "created_at": now,
                **_record_payload(root, request["kind"], request["id"], source),
            }
        else:
            record = dict(record)
        history_path = project_path(root, f"{DIRECTORY}/{record_id}.json")
        if (history_path.read_bytes() if history_path.exists() else None) != previous_record:
            raise ResourceConflict("El registro cambió durante la operación")
        record["status"] = "pending"
        pending_bytes = _json(record)
        _write(history_path, pending_bytes, create=previous_record is None)
        written = False
        final_bytes = None
        try:
            if (
                _sources(root) != source_files
                or (target.read_bytes() if target.exists() else None) != original
            ):
                raise ResourceConflict("Edición externa durante la operación")
            if content is None:
                target.unlink()
            else:
                _write(target, content, create=original is None)
            written = True
            record["status"] = {
                "archive": "archived",
                "restore": "restored",
                "duplicate": "duplicated",
            }[action]
            if action == "restore":
                record["restored_at"] = now
            if history_path.read_bytes() != pending_bytes:
                raise ResourceConflict("El registro cambió externamente")
            final_bytes = _json(record)
            _write(history_path, final_bytes)
        except Exception as error:
            try:
                current = target.read_bytes() if target.exists() else None
                if written and current == content:
                    if original is None:
                        target.unlink()
                    else:
                        _write(target, original)
                elif written:
                    raise ResourceConflict("Hay una edición externa posterior; se conserva")
                if history_path.read_bytes() not in (pending_bytes, final_bytes):
                    raise ResourceConflict("Edición externa del registro; se conserva")
                if previous_record is not None:
                    _write(history_path, previous_record)
                else:
                    record["status"] = "failed"
                    _write(history_path, _json(record))
            except Exception:
                raise RuntimeError(
                    f"Operación interrumpida; revisar recurso y copia en {history_path}"
                ) from error
            raise
        return {
            **plan,
            "applied": True,
            "archive_id": record_id,
            "next": "Revisar diff y preparar la integración; historial y snapshots existentes se conservan.",
        }
