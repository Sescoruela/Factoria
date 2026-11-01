from __future__ import annotations

import re
import shlex
from datetime import date
from pathlib import Path
from types import MappingProxyType

from factoria.domain.models import (
    ConfirmedCommand,
    MemoryMetadata,
    ModuleMemory,
    ProjectKind,
    ProjectMemory,
)

_METADATA_RE = re.compile(
    r"^<!-- factoria-memory: type=(?P<type>[^|]+) \| "
    r"reviewed_commit=(?P<commit>[^|]+) \| date=(?P<date>[^|]+) \| "
    r"factoria=(?P<version>[^ ]+) -->$"
)
_COMMAND_RE = re.compile(
    r"^- \*\*(?P<category>[^/]+) / (?P<scope>[^*]+)\*\* "
    r"\((?P<meta>[^)]*)\): (?P<command>.+)$"
)
_LEGACY_COMMAND_RE = re.compile(r"^- \*\*(?P<category>[^*]+)\*\*: (?P<commands>.+)$")
_MODULE_RE = re.compile(r"^- \*\*(?P<name>[^*]+)\*\*: (?P<body>.+)$")
_DEP_RE = re.compile(r"^- \*\*(?P<source>[^*]+)\*\* → (?P<targets>.+)$")


class MemoryFormatError(ValueError):
    """Raised when persisted memory cannot be reconstructed safely."""


def _sections(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            current = line[3:].strip()
            result[current] = []
            continue
        if current is not None:
            result[current].append(line)
    return result


def _nonempty(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def _bullets(lines: list[str], *, ignore_prefixes: tuple[str, ...] = ()) -> tuple[str, ...]:
    values: list[str] = []
    for line in _nonempty(lines):
        if not line.startswith("- "):
            continue
        value = line[2:].strip()
        if any(value.startswith(prefix) for prefix in ignore_prefixes):
            continue
        values.append(value)
    return tuple(values)


def _metadata(first_line: str) -> MemoryMetadata:
    match = _METADATA_RE.fullmatch(first_line.strip())
    if match is None:
        raise MemoryFormatError("AGENTS.md does not contain a supported Factoria memory header")
    try:
        return MemoryMetadata(
            reviewed_commit=match.group("commit").strip(),
            reviewed_at=date.fromisoformat(match.group("date").strip()),
            factoria_version=match.group("version").strip(),
            project_kind=ProjectKind(match.group("type").strip()),
        )
    except ValueError as exc:
        raise MemoryFormatError(f"Invalid Factoria memory metadata: {exc}") from exc


def _parse_module_line(line: str) -> ModuleMemory:
    match = _MODULE_RE.fullmatch(line)
    if match is None:
        raise MemoryFormatError(f"Unsupported module entry: {line}")
    body = match.group("body")
    path_part, separator, affects_part = body.partition("; afecta a:")
    path_part = path_part.strip()
    paths = () if path_part == "sin rutas confirmadas" else tuple(
        item.strip() for item in path_part.split(",") if item.strip()
    )
    affects = () if not separator else tuple(
        item.strip() for item in affects_part.split(",") if item.strip()
    )
    return ModuleMemory(name=match.group("name").strip(), paths=paths, affects=affects)


def _modules(lines: list[str]) -> tuple[ModuleMemory, ...]:
    result: list[ModuleMemory] = []
    for line in _nonempty(lines):
        if line in {"- Sin módulos confirmados", "- Pendiente de documentar"}:
            continue
        result.append(_parse_module_line(line))
    return tuple(result)


def _commands(lines: list[str]) -> tuple[tuple[ConfirmedCommand, ...], MappingProxyType]:
    modern: list[ConfirmedCommand] = []
    legacy: dict[str, list[tuple[str, ...]]] = {}
    for line in _nonempty(lines):
        if line in {"- Ninguno confirmado todavía", "- No hay comandos de verificación confirmados"}:
            continue
        match = _COMMAND_RE.fullmatch(line)
        if match is not None:
            meta = {item.strip() for item in match.group("meta").split(",") if item.strip()}
            scope_value = match.group("scope").strip()
            try:
                argv = tuple(shlex.split(match.group("command")))
            except ValueError as exc:
                raise MemoryFormatError(f"Invalid confirmed command quoting: {line}") from exc
            modern.append(
                ConfirmedCommand(
                    category=match.group("category").strip(),
                    scope=None if scope_value == "global" else scope_value,
                    command=argv,
                    required="obligatorio" in meta,
                    global_check="global" in meta,
                )
            )
            continue
        legacy_match = _LEGACY_COMMAND_RE.fullmatch(line)
        if legacy_match is None:
            raise MemoryFormatError(f"Unsupported confirmed command entry: {line}")
        category = legacy_match.group("category").strip()
        for raw_command in legacy_match.group("commands").split(";"):
            try:
                argv = tuple(shlex.split(raw_command.strip()))
            except ValueError as exc:
                raise MemoryFormatError(f"Invalid legacy command quoting: {line}") from exc
            if argv:
                legacy.setdefault(category, []).append(argv)
    frozen_legacy = MappingProxyType(
        {category: tuple(commands) for category, commands in legacy.items()}
    )
    return tuple(modern), frozen_legacy


def _dependencies(lines: list[str]) -> MappingProxyType:
    values: dict[str, tuple[str, ...]] = {}
    for line in _nonempty(lines):
        if line in {"- Sin dependencias confirmadas", "- Pendiente de documentar"}:
            continue
        match = _DEP_RE.fullmatch(line)
        if match is None:
            raise MemoryFormatError(f"Unsupported dependency entry: {line}")
        values[match.group("source").strip()] = tuple(
            item.strip() for item in match.group("targets").split(",") if item.strip()
        )
    return MappingProxyType(values)


def _document_bullets(path: Path, heading: str) -> tuple[str, ...]:
    if not path.exists():
        return ()
    sections = _sections(path.read_text(encoding="utf-8"))
    return _bullets(
        sections.get(heading, []),
        ignore_prefixes=("Sin ", "No hay ", "Pendiente"),
    )


def _root_bullets(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    values: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if not value.startswith(("Sin ", "No hay ", "Pendiente")):
                values.append(value)
    return tuple(values)


def load_project_memory(project_root: Path) -> ProjectMemory:
    root = project_root.resolve()
    agents = root / "AGENTS.md"
    if not agents.exists():
        raise FileNotFoundError("No project memory found; run `factoria memoria-init` first")

    text = agents.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 2 or not lines[1].startswith("# "):
        raise MemoryFormatError("AGENTS.md is missing the Factoria project heading")

    metadata = _metadata(lines[0])
    sections = _sections(text)
    purpose_lines = _nonempty(sections.get("Propósito", []))
    purpose = "\n".join(purpose_lines)
    if purpose == "Pendiente de confirmar.":
        purpose = ""

    technologies = _bullets(
        sections.get("Tecnologías", []),
        ignore_prefixes=("Sin datos confirmados",),
    )
    modules = _modules(sections.get("Módulos", []))
    commands, legacy_commands = _commands(sections.get("Comandos confirmados", []))
    mandatory_rules = _bullets(
        sections.get("Reglas obligatorias", []),
        ignore_prefixes=("Sin datos confirmados",),
    )
    non_functional_priorities = _bullets(
        sections.get("Prioridades no funcionales", []),
        ignore_prefixes=("Sin datos confirmados",),
    )
    dependencies = _dependencies(sections.get("Dependencias", []))

    docs = root / "docs" / "memoria"
    architecture = docs / "arquitectura.md"
    if architecture.exists():
        architecture_sections = _sections(architecture.read_text(encoding="utf-8"))
        architecture_modules = _modules(architecture_sections.get("Módulos", []))
        if architecture_modules:
            by_name = {module.name: module for module in modules}
            for module in architecture_modules:
                by_name[module.name] = module
            modules = tuple(by_name.values())
        architecture_priorities = _bullets(
            architecture_sections.get("Prioridades no funcionales", []),
            ignore_prefixes=("Sin datos confirmados",),
        )
        if architecture_priorities:
            non_functional_priorities = architecture_priorities

    decisions = _root_bullets(docs / "decisiones.md")
    manual_verification = _document_bullets(
        docs / "testing.md", "Cómo comprobarlo a mano"
    )

    return ProjectMemory(
        project_name=lines[1][2:].strip(),
        purpose=purpose,
        metadata=metadata,
        technologies=technologies,
        modules=modules,
        dependencies=dependencies,
        confirmed_commands=legacy_commands,
        confirmed_check_commands=commands,
        mandatory_rules=mandatory_rules,
        non_functional_priorities=non_functional_priorities,
        decisions=decisions,
        manual_verification=manual_verification,
    )
