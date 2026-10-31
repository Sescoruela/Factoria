from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from factoria.domain.models import MemoryDocumentKind, ProjectKind
from factoria.domain.permissions import PermissionProfile


@dataclass(frozen=True, slots=True)
class OrganizationConfig:
    blocked_actions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class GlobalConfig:
    default_profile: PermissionProfile = PermissionProfile.NORMAL
    default_tool: str | None = None
    max_agents: int = 2
    personal_plugin_paths: tuple[Path, ...] = field(default_factory=tuple)
    organization_plugin_paths: tuple[Path, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    project_kind: ProjectKind | None = None
    stale_after_commits: Mapping[MemoryDocumentKind, int] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    profile: PermissionProfile | None = None
    max_agents: int | None = None
    allowed_flows: tuple[str, ...] = field(default_factory=tuple)
    blocked_flows: tuple[str, ...] = field(default_factory=tuple)
    blocked_actions: tuple[str, ...] = field(default_factory=tuple)
    memory: MemoryConfig = field(default_factory=MemoryConfig)


@dataclass(frozen=True, slots=True)
class RuntimeOverrides:
    profile: PermissionProfile | None = None
    tool: str | None = None
    max_agents: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    profile: PermissionProfile
    tool: str | None
    max_agents: int
    allowed_flows: tuple[str, ...]
    blocked_flows: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    personal_plugin_paths: tuple[Path, ...]
    organization_plugin_paths: tuple[Path, ...]
    memory: MemoryConfig
