from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class PluginType(StrEnum):
    ADAPTER = "adapter"
    PACK = "pack"
    CHECK = "check"
    FLOW = "flow"


class ProjectKind(StrEnum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"


class MemoryDocumentKind(StrEnum):
    ARCHITECTURE = "architecture"
    FLOWS = "flows"
    DECISIONS = "decisions"
    TESTING = "testing"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    required: bool
    details: str | None = None


@dataclass(frozen=True, slots=True)
class PluginManifest:
    name: str
    version: str
    plugin_type: PluginType
    description: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    factoria_compatibility: str = ">=0.1.0"
    entrypoint: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryMetadata:
    reviewed_commit: str
    reviewed_at: date
    factoria_version: str
    project_kind: ProjectKind


@dataclass(frozen=True, slots=True)
class ModuleMemory:
    name: str
    paths: tuple[str, ...] = field(default_factory=tuple)
    affects: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ConfirmedCommand:
    category: str
    command: tuple[str, ...]
    scope: str | None = None
    required: bool = True
    global_check: bool = False

    def __post_init__(self) -> None:
        if not self.category.strip():
            raise ValueError("Confirmed command category cannot be empty")
        if not self.command or not all(part.strip() for part in self.command):
            raise ValueError("Confirmed command must contain non-empty argv parts")


@dataclass(frozen=True, slots=True)
class ProjectMemory:
    project_name: str
    purpose: str = ""
    metadata: MemoryMetadata | None = None
    technologies: tuple[str, ...] = field(default_factory=tuple)
    modules: tuple[ModuleMemory, ...] = field(default_factory=tuple)
    dependencies: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    # Legacy command format kept temporarily for backward compatibility.
    confirmed_commands: Mapping[str, tuple[tuple[str, ...], ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    confirmed_check_commands: tuple[ConfirmedCommand, ...] = field(default_factory=tuple)
    mandatory_rules: tuple[str, ...] = field(default_factory=tuple)
    decisions: tuple[str, ...] = field(default_factory=tuple)
    manual_verification: tuple[str, ...] = field(default_factory=tuple)
