from __future__ import annotations

import tomllib
from pathlib import Path
from types import MappingProxyType
from typing import Any

from factoria.domain.models import MemoryDocumentKind, ProjectKind
from factoria.domain.permissions import PermissionProfile

from .models import (
    GlobalConfig,
    MemoryConfig,
    OrganizationConfig,
    ProjectConfig,
    ResolvedConfig,
    RuntimeOverrides,
)


class ConfigError(ValueError):
    """Raised when configuration is malformed or unsafe."""


_ALLOWED_ACTIONS = {"read", "write", "command", "destructive"}


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc


def _profile(value: object, *, field_name: str) -> PermissionProfile | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{field_name} must be a string")
    try:
        return PermissionProfile(value)
    except ValueError as exc:
        allowed = ", ".join(profile.value for profile in PermissionProfile)
        raise ConfigError(f"{field_name} must be one of: {allowed}") from exc


def _positive_int(value: object, *, field_name: str, default: int | None = None) -> int | None:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{field_name} must be a positive integer")
    return value


def _paths(values: object, *, base: Path) -> tuple[Path, ...]:
    if values is None:
        return ()
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ConfigError("Plugin paths must be a list of strings")
    result: list[Path] = []
    for item in values:
        path = Path(item).expanduser()
        if not path.is_absolute():
            path = base / path
        result.append(path.resolve())
    return tuple(result)


def _blocked_actions(values: object, *, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ConfigError(f"{field_name} must be a list of strings")
    unknown = sorted(set(values) - _ALLOWED_ACTIONS)
    if unknown:
        raise ConfigError(
            f"{field_name} contains unknown actions: {', '.join(unknown)}; "
            f"expected: {', '.join(sorted(_ALLOWED_ACTIONS))}"
        )
    return tuple(dict.fromkeys(values))


def _memory_config(data: object) -> MemoryConfig:
    if data is None:
        return MemoryConfig()
    if not isinstance(data, dict):
        raise ConfigError("[memory] must be a TOML table")

    raw_kind = data.get("type")
    project_kind: ProjectKind | None = None
    if raw_kind is not None:
        if not isinstance(raw_kind, str):
            raise ConfigError("memory.type must be a string")
        try:
            project_kind = ProjectKind(raw_kind)
        except ValueError as exc:
            allowed = ", ".join(kind.value for kind in ProjectKind)
            raise ConfigError(f"memory.type must be one of: {allowed}") from exc

    staleness = data.get("staleness", {})
    if not isinstance(staleness, dict):
        raise ConfigError("[memory.staleness] must be a TOML table")

    thresholds: dict[MemoryDocumentKind, int] = {}
    for raw_document, raw_value in staleness.items():
        try:
            document = MemoryDocumentKind(raw_document)
        except ValueError as exc:
            allowed = ", ".join(document.value for document in MemoryDocumentKind)
            raise ConfigError(
                f"Unknown memory staleness document {raw_document!r}; expected one of: {allowed}"
            ) from exc
        value = _positive_int(raw_value, field_name=f"memory.staleness.{raw_document}")
        assert value is not None
        thresholds[document] = value

    return MemoryConfig(
        project_kind=project_kind,
        stale_after_commits=MappingProxyType(thresholds),
    )


def load_organization_config(path: Path) -> OrganizationConfig:
    data = _read_toml(path)
    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        raise ConfigError("[permissions] must be a TOML table")
    return OrganizationConfig(
        blocked_actions=_blocked_actions(
            permissions.get("blocked_actions"),
            field_name="permissions.blocked_actions",
        )
    )


def load_global_config(path: Path) -> GlobalConfig:
    data = _read_toml(path)
    plugins = data.get("plugins", {})
    if not isinstance(plugins, dict):
        raise ConfigError("[plugins] must be a TOML table")

    tool = data.get("default_tool")
    if tool is not None and not isinstance(tool, str):
        raise ConfigError("default_tool must be a string")

    return GlobalConfig(
        default_profile=_profile(data.get("default_profile"), field_name="default_profile")
        or PermissionProfile.NORMAL,
        default_tool=tool,
        max_agents=_positive_int(data.get("max_agents"), field_name="max_agents", default=2)
        or 2,
        personal_plugin_paths=_paths(plugins.get("personal_paths"), base=path.parent),
        organization_plugin_paths=_paths(
            plugins.get("organization_paths"), base=path.parent
        ),
    )


def load_project_config(path: Path) -> ProjectConfig:
    data = _read_toml(path)
    if "default_tool" in data:
        raise ConfigError(
            "Projects cannot define default_tool; tool preference is global or per execution"
        )

    flows = data.get("flows", {})
    if not isinstance(flows, dict):
        raise ConfigError("[flows] must be a TOML table")

    allowed = flows.get("allowed", [])
    blocked = flows.get("blocked", [])
    for name, value in (("allowed", allowed), ("blocked", blocked)):
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigError(f"flows.{name} must be a list of strings")

    overlap = set(allowed) & set(blocked)
    if overlap:
        joined = ", ".join(sorted(overlap))
        raise ConfigError(f"Flows cannot be both allowed and blocked: {joined}")

    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        raise ConfigError("[permissions] must be a TOML table")

    return ProjectConfig(
        profile=_profile(data.get("profile"), field_name="profile"),
        max_agents=_positive_int(data.get("max_agents"), field_name="max_agents"),
        allowed_flows=tuple(allowed),
        blocked_flows=tuple(blocked),
        blocked_actions=_blocked_actions(
            permissions.get("blocked_actions"),
            field_name="permissions.blocked_actions",
        ),
        memory=_memory_config(data.get("memory")),
    )


def resolve_config(
    global_config: GlobalConfig,
    project_config: ProjectConfig | None = None,
    overrides: RuntimeOverrides | None = None,
) -> ResolvedConfig:
    project_config = project_config or ProjectConfig()
    overrides = overrides or RuntimeOverrides()

    return ResolvedConfig(
        profile=overrides.profile or project_config.profile or global_config.default_profile,
        tool=overrides.tool if overrides.tool is not None else global_config.default_tool,
        max_agents=overrides.max_agents or project_config.max_agents or global_config.max_agents,
        allowed_flows=project_config.allowed_flows,
        blocked_flows=project_config.blocked_flows,
        blocked_actions=project_config.blocked_actions,
        personal_plugin_paths=global_config.personal_plugin_paths,
        organization_plugin_paths=global_config.organization_plugin_paths,
        memory=project_config.memory,
    )
