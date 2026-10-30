from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from factoria.domain.permissions import PermissionProfile

from .models import GlobalConfig, ProjectConfig, ResolvedConfig, RuntimeOverrides


class ConfigError(ValueError):
    """Raised when configuration is malformed or unsafe."""


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

    return ProjectConfig(
        profile=_profile(data.get("profile"), field_name="profile"),
        max_agents=_positive_int(data.get("max_agents"), field_name="max_agents"),
        allowed_flows=tuple(allowed),
        blocked_flows=tuple(blocked),
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
        personal_plugin_paths=global_config.personal_plugin_paths,
        organization_plugin_paths=global_config.organization_plugin_paths,
    )
