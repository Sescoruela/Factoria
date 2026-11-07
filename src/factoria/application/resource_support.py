"""Shared resource serialization, validation and catalog revisions. No template dependencies."""

from __future__ import annotations
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
from factoria.security import SecretScanner


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def scan_secrets(value):
    if isinstance(value, str) and SecretScanner().scan_text(value, location="template"):
        raise ValueError("Posible secreto en la plantilla; no se exporta ni aplica")
    if isinstance(value, dict):
        for item in value.values():
            scan_secrets(item)
    if isinstance(value, (list, tuple)):
        for item in value:
            scan_secrets(item)


def catalog_locks():
    """Acquire catalog locks in the one shared order used by multi-resource operations."""
    from factoria.application.resource_locks import SKILL_LOCK, AGENT_LOCK, WORKFLOW_LOCK

    stack = ExitStack()
    for lock in (SKILL_LOCK, AGENT_LOCK, WORKFLOW_LOCK):
        stack.enter_context(lock)
    return stack


def catalog_revision(root: Path) -> str:
    from factoria.application import (
        agent_profiles as agents,
        skill_catalog as skills,
        workflow_presets as workflows,
    )

    values = [
        str(root.resolve()),
        skills.skill_catalog_revision(root),
        agents.agent_catalog_revision(root),
        workflows.workflow_catalog_revision(root),
    ]
    return hashlib.sha256(json_bytes(values)).hexdigest()


def skill_bytes(raw) -> bytes:
    header = "\n".join(
        f"{key}: {json.dumps(raw.get(key, ''), ensure_ascii=False)}"
        for key in ("id", "name", "description")
    )
    return ("<!-- factoria:skill:v1 -->\n---\n" + header + "\n---\n" + raw["content"]).encode(
        "utf-8"
    )


def read_catalog(root: Path, current: str, legacy: str) -> dict:
    from factoria.project_paths import project_path

    target = project_path(root, current)
    if not target.exists():
        target = project_path(root, legacy)
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
