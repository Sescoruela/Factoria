from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


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
    plugin_type: str
    description: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    factoria_compatibility: str = ">=0.1.0"


@dataclass(frozen=True, slots=True)
class ProjectMemory:
    project_name: str
    decisions: tuple[str, ...] = field(default_factory=tuple)
    modules: tuple[str, ...] = field(default_factory=tuple)
    dependencies: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    confirmed_commands: Mapping[str, tuple[tuple[str, ...], ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
