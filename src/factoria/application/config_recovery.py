"""Bounded, reviewed configuration migrations/checkpoints with durable recovery.

Copies are local Git metadata, never portable templates or workflow snapshots.
A pending transaction can only restore bytes it actually owned.
"""

from __future__ import annotations

from factoria.storage import atomic_write_bytes, sync_directory

import base64
from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from factoria.application.config_schema import SCHEMA_PATH, schema_version
from factoria.project_paths import project_path
from factoria.application.resource_support import (
    catalog_locks as _locks,
    json_bytes as _json,
    scan_secrets as _scan,
)

FIXED = {
    SCHEMA_PATH,
    ".factoria/config.toml",
    ".factoria/agents.json",
    ".factoria/workflows.json",
    ".factoria/ui-agents.json",
    ".factoria/ui-workflows.json",
}
LIMIT = 8 * 1024 * 1024


def _allowed(name):
    return name in FIXED or bool(
        re.fullmatch(
            r"\.factoria/skills/[a-zA-Z0-9_-]+\.md|\.factoria/archive/[0-9a-f]{32}\.json", name
        )
    )


def _capture(root):
    names = set(FIXED)
    for folder, suffix in ((".factoria/skills", ".md"), (".factoria/archive", ".json")):
        directory = project_path(root, folder)
        if directory.exists():
            entries = list(directory.iterdir())
            if len(entries) > 2048:
                raise ValueError("Demasiados archivos de configuración")
            names.update(
                p.relative_to(root).as_posix() for p in entries if p.suffix.lower() == suffix
            )
    data = {}
    size = 0
    for name in sorted(names):
        if not _allowed(name):
            raise ValueError("Ruta de configuración no soportada en recuperación")
        path = project_path(root, name)
        if path.exists():
            if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Archivo de configuración demasiado grande")
            size += path.stat().st_size
            if size > LIMIT:
                raise ValueError("Configuración supera 8 MiB")
            data[name] = path.read_bytes()
        else:
            data[name] = None
    return data


def _digest(data):
    return hashlib.sha256(
        _json(
            {
                k: None if v is None else hashlib.sha256(v).hexdigest()
                for k, v in sorted(data.items())
            }
        )
    ).hexdigest()


def _safe(data):
    for value in data.values():
        if value is not None:
            _scan(value.decode("utf-8"))


def _folder(root):
    found = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", "factoria/config-recovery"],
        capture_output=True,
        text=True,
    )
    if found.returncode:
        return None
    folder = Path(found.stdout.strip())
    if not folder.is_absolute():
        folder = root / folder
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise ValueError("Copia local con symlink no permitida")
    return folder


def _unpack(values):
    if not isinstance(values, dict) or len(values) > 4102 or not FIXED <= set(values):
        raise ValueError("Inventario de copia no válido")
    result = {}
    for name, value in values.items():
        if not _allowed(name):
            raise ValueError("Ruta de copia no válida")
        if value is not None and not isinstance(value, str):
            raise ValueError("Contenido de copia no válido")
        result[name] = None if value is None else base64.b64decode(value, validate=True)
        if result[name] is not None and len(result[name]) > 2 * 1024 * 1024:
            raise ValueError("Archivo de copia demasiado grande")
    if sum(len(v) for v in result.values() if v is not None) > LIMIT:
        raise ValueError("Copia demasiado grande")
    _safe(result)
    return result


def _record(root, identifier):
    if not isinstance(identifier, str) or not re.fullmatch("[0-9a-f]{32}", identifier):
        raise ValueError("Identificador de copia no válido")
    folder = _folder(root)
    if folder is None:
        raise ValueError("Se requiere un repositorio Git")
    path = folder / (identifier + ".json")
    if path.is_symlink() or path.stat().st_size > 24 * 1024 * 1024:
        raise ValueError("Copia local no válida")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Copia con claves duplicadas")
            result[key] = value
        return result

    record = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    fields = {
        "schema_version",
        "id",
        "project",
        "kind",
        "state",
        "created",
        "before",
        "after",
        "before_hash",
        "after_hash",
    }
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("Registro de recuperación no válido")
    if not isinstance(record["created"], str) or len(record["created"]) > 40:
        raise ValueError("Fecha de copia no válida")
    datetime.fromisoformat(record["created"])
    if (
        record.get("schema_version") != 1
        or type(record.get("schema_version")) is not int
        or record.get("id") != identifier
        or record.get("project") != str(root.resolve())
        or record.get("kind") not in ("migration", "checkpoint", "restore")
        or record.get("state") not in ("pending", "complete", "restored")
    ):
        raise ValueError("Registro de recuperación no válido o de otro proyecto")
    if not all(
        key in record for key in ("before", "after", "before_hash", "after_hash", "created")
    ):
        raise ValueError("Copia incompleta")
    for side in ("before", "after"):
        decoded = _unpack(record[side])
        if _digest(decoded) != record[side + "_hash"]:
            raise ValueError("Copia corrupta; no se restaura")
    return record


def _records(root):
    folder = _folder(root)
    if folder is None or not folder.exists():
        return []
    paths = list(folder.iterdir())
    if len(paths) > 256:
        raise ValueError("Demasiadas copias; archivar manualmente antes de continuar")
    return [_record(root, p.stem) for p in sorted(paths) if p.suffix == ".json"]


def pending_recoveries(root):
    return [r["id"] for r in _records(root) if r["state"] == "pending"]


def _validate(data):
    # Validate a candidate with existing parsers, without writing into the project.
    from factoria.application.agent_profiles import load_agent_profiles
    from factoria.application.workflow_presets import load_catalog
    from factoria.application.skill_catalog import skill_catalog_snapshot
    from factoria.application.resource_archive import archive_records
    from factoria.config.loader import load_project_config

    with tempfile.TemporaryDirectory(prefix="factoria-config-validation-") as tmp:
        root = Path(tmp)
        for name, content in data.items():
            if content is not None:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        schema_version(root)
        load_project_config(root / ".factoria/config.toml")
        load_agent_profiles(root)
        skill_catalog_snapshot(root)
        load_catalog(root)
        archive_records(root)


def config_status(root):
    root = root.resolve()
    try:
        version, error = schema_version(root), None
    except (ValueError, OSError) as exc:
        version, error = None, str(exc)
    return {
        "project_path": str(root),
        "schema_version": version,
        "error": error,
        "backups": [{k: r[k] for k in ("id", "kind", "state", "created")} for r in _records(root)],
    }


def _plan(root, action, identifier=None):
    version = schema_version(root)
    before = _capture(root)
    _safe(before)
    after = dict(before)
    conflicts = []
    record = None
    pending = pending_recoveries(root)
    if action == "restore":
        record = _record(root, identifier)
        if any(i != identifier for i in pending):
            conflicts.append("Recuperar primero la otra operación pendiente")
        desired = _unpack(record["before"])
        after = {name: desired.get(name) for name in set(before) | set(desired)}
        if record["state"] == "pending":
            planned = _unpack(record["after"])
            for name in set(before) | set(desired) | set(planned):
                if before.get(name) not in (desired.get(name), planned.get(name)):
                    conflicts.append("Cambio externo: " + name)
        _validate(after)
    elif action in ("migrate", "snapshot"):
        if pending:
            conflicts.append("Hay una recuperación pendiente")
        _validate(before)
        if action == "migrate" and version == 0:
            for current, legacy in (
                (".factoria/agents.json", ".factoria/ui-agents.json"),
                (".factoria/workflows.json", ".factoria/ui-workflows.json"),
            ):
                if before[legacy] is not None:
                    if before[current] is None:
                        after[current] = before[legacy]
                    elif json.loads(before[current]) != json.loads(before[legacy]):
                        conflicts.append("Catálogos actual/legacy divergentes: " + current)
            after[SCHEMA_PATH] = _json({"schema_version": 1})
            _validate(after)
    else:
        raise ValueError("Operación de configuración no válida")
    if _capture(root) != before:
        raise ValueError("La configuración cambió durante el preview")
    changed = [
        name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)
    ]
    token = hashlib.sha256(
        _json([str(root), action, identifier, _digest(before), _digest(after), record, pending])
    ).hexdigest()
    preview = {
        "project_path": str(root),
        "action": action,
        "backup_id": identifier,
        "schema_version": version,
        "changed": changed,
        "removed": [name for name in changed if after.get(name) is None],
        "conflicts": conflicts,
        "token": token,
    }
    return preview, before, after, record


def preview_config(root, action, identifier=None):
    with _locks():
        return _plan(root.resolve(), action, identifier)[0]


_sync_directory = sync_directory


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is None:
        path.unlink(missing_ok=True)
        _sync_directory(path.parent)
        return
    atomic_write_bytes(path, content)
    _sync_directory(path.parent)


def _save_record(root, record):
    folder = _folder(root)
    if folder is None:
        raise ValueError("Se requiere un repositorio Git")
    folder.mkdir(parents=True, exist_ok=True)
    _sync_directory(folder.parent)
    target = folder / (record["id"] + ".json")
    if target.is_symlink():
        raise ValueError("Copia local con symlink no permitida")
    _write(folder / (record["id"] + ".json"), _json(record))


def apply_config(root, action, *, identifier=None, token, confirmed):
    if not confirmed:
        raise PermissionError("Revisar preview y confirmar explícitamente")
    root = root.resolve()
    from factoria.application.governance import ExecutionGovernor, GovernedAction
    from factoria.application.policy_runtime import build_execution_context

    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(root))
    with _locks():
        plan, before, after, old = _plan(root, action, identifier)
        if token != plan["token"] or plan["conflicts"]:
            raise ValueError("Preview obsoleto o con conflictos; volver a revisar")
        if action == "migrate" and not plan["changed"]:
            return {**plan, "applied": True, "backup_id": None}
        recovering = old is not None and old["state"] == "pending"
        if recovering:
            record = old
        else:
            if len(_records(root)) >= 256:
                raise ValueError(
                    "Límite de copias alcanzado; archivar copias antiguas antes de continuar"
                )

            def pack(values):
                return {
                    k: None if v is None else base64.b64encode(v).decode("ascii")
                    for k, v in values.items()
                }

            record = {
                "schema_version": 1,
                "id": uuid.uuid4().hex,
                "kind": {"migrate": "migration", "snapshot": "checkpoint", "restore": "restore"}[
                    action
                ],
                "project": str(root),
                "state": "pending",
                "created": datetime.now(UTC).isoformat(),
                "before": pack(before),
                "after": pack(after),
                "before_hash": _digest(before),
                "after_hash": _digest(after),
            }
            _save_record(
                root, record
            )  # Durable intent and all original bytes before touching configuration.
        try:
            if _capture(root) != before:
                raise ValueError("Cambio externo antes de escribir")
            for name in plan["changed"]:
                path = project_path(root, name)
                if (path.read_bytes() if path.exists() else None) != before.get(name):
                    raise ValueError("Cambio externo durante la operación")
                _write(path, after.get(name))
            actual = _capture(root)
            if any(actual.get(k) != after.get(k) for k in set(actual) | set(after)):
                raise ValueError("Cambio externo durante la operación")
            record["state"] = "restored" if recovering else "complete"
            _save_record(root, record)
        except Exception as exc:
            raise ValueError(
                "Operación interrumpida; revisar y restaurar la copia " + record["id"]
            ) from exc
        return {**plan, "applied": True, "backup_id": record["id"]}
