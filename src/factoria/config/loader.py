from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from factoria.domain.permissions import PermissionProfile

from .models import GlobalConfig, ProjectConfig, ResolvedConfig


class ConfigError(ValueError):
    """Raised when configuration is malformed or unsafe."""


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _profile(value: str | None, *, field_name: str) -> PermissionProfile | None:
    if value is None:
        return None
    try:
        return PermissionProfile(value)
    except ValueError as exc:
        raise ConfigError(f"Invalid {field_name}: {value}") from exc


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


def load_global_config(path: Path) -> GlobalConfig:
    data = _read_toml(path)
    plugins = data.get("plugins", {})
    if not isinstance(plugins, dict):
        raise ConfigError("[plugins] must be a TOML table")

    profile = _profile(data.get("default_profile"), field_name="default_profile")
    tool = data.get("default_tool")
    if tool is not None and not isinstance(tool, str):
        raise ConfigError("default_tool must be a string")

    return GlobalConfig(
        default_profile=profile or PermissionProfile.NORMAL,
        default_tool=tool,
        personal_plugin_paths=_paths(plugins.get("personal_paths"), base=path.parent),
        organization_plugin_paths=_paths(plugins.get("organization_paths"), base=path.parent),
    )


def load_project_config(path: Path) -> ProjectConfig:
    data = _read_toml(path)
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

    return ProjectConfig(
        profile=_profile(data.get("profile"), field_name="profile"),
        allowed_flows=tuple(allowed),
        blocked_flows=tuple(blocked),
    )


def resolve_config(global_config: GlobalConfig, project_config: ProjectConfig) -> ResolvedConfig:
    return ResolvedConfig(
        profile=project_config.profile or global_config.default_profile,
        tool=global_config.default_tool,
        allowed_flows=project_config.allowed_flows,
        blocked_flows=project_config.blocked_flows,
        personal_plugin_paths=global_config.personal_plugin_paths,
        organization_plugin_paths=global_config.organization_plugin_paths,
    )
