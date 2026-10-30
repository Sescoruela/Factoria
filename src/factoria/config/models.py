from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from factoria.domain.permissions import PermissionProfile


@dataclass(frozen=True, slots=True)
class GlobalConfig:
    default_profile: PermissionProfile = PermissionProfile.NORMAL
    default_tool: str | None = None
    max_agents: int = 2
    personal_plugin_paths: tuple[Path, ...] = field(default_factory=tuple)
    organization_plugin_paths: tuple[Path, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    profile: PermissionProfile | None = None
    max_agents: int | None = None
    allowed_flows: tuple[str, ...] = field(default_factory=tuple)
    blocked_flows: tuple[str, ...] = field(default_factory=tuple)


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
    personal_plugin_paths: tuple[Path, ...]
    organization_plugin_paths: tuple[Path, ...]
