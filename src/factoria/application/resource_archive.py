"""Archive identity and revisions shared by editors and template imports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

DIRECTORY = ".factoria/archive"


def archive_records(root: Path) -> dict[str, dict]:
    from factoria.application.project_integration import project_path

    folder = project_path(root, DIRECTORY)
    if not folder.exists():
        return {}
    if not folder.is_dir():
        raise ValueError("El archivo de recursos debe ser una carpeta")
    records = {}
    for file in sorted(folder.glob("*.json")):
        if not re.fullmatch(r"[0-9a-f]{32}\.json", file.name):
            raise ValueError("Nombre de registro archivado no válido")
        target = project_path(root, f"{DIRECTORY}/{file.name}")
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Registro archivado demasiado grande")
        data = json.loads(target.read_text(encoding="utf-8"))
        if (
            not isinstance(data, dict)
            or type(data.get("schema_version")) is not int
            or data.get("schema_version") != 1
            or data.get("kind") not in ("skill", "agent", "workflow")
            or not isinstance(data.get("id"), str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", data["id"])
            or data.get("status") not in ("pending", "archived", "restored", "duplicated", "failed")
            or not isinstance(data.get("resource"), dict)
            or not isinstance(data.get("raw"), str if data.get("kind") == "skill" else dict)
        ):
            raise ValueError("Registro archivado no válido; revisar antes de modificar recursos")
        records[file.stem] = data
    return records


def archive_revision(root: Path) -> str:
    return hashlib.sha256(
        json.dumps(archive_records(root), ensure_ascii=True, sort_keys=True).encode()
    ).hexdigest()


def assert_not_archived(root: Path, kind: str, identifier: str) -> None:
    for record in archive_records(root).values():
        if (
            record["kind"] == kind
            and record["id"] == identifier
            and (record["status"] in ("archived", "pending") or record.get("recovery_required"))
        ):
            raise ValueError(
                f"El identificador {identifier} está archivado o pendiente de recuperación; restaurar antes de reutilizar"
            )
