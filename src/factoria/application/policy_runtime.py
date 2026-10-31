from __future__ import annotations

from pathlib import Path

from factoria.config.loader import (
    load_global_config,
    load_organization_config,
    load_project_config,
)
from factoria.domain.permissions import PermissionProfile

from .governance import ExecutionContext, GovernedAction, PolicyLevel, PolicyRule


def build_execution_context(
    project_root: Path,
    *,
    requested_profile: PermissionProfile | None = None,
    flow_authorized: bool = False,
    destructive_confirmed: bool = False,
) -> ExecutionContext:
    global_config = load_global_config(Path.home() / ".factoria" / "config.toml")
    organization = load_organization_config(Path.home() / ".factoria" / "organization.toml")
    project = load_project_config(project_root / ".factoria" / "config.toml")
    base_profile = project.profile or global_config.default_profile

    rules: list[PolicyRule] = []
    for raw_action in organization.blocked_actions:
        rules.append(
            PolicyRule(
                level=PolicyLevel.ORGANIZATION,
                action=GovernedAction(raw_action),
                allowed=False,
                reason=f"Organization policy blocks {raw_action} actions",
            )
        )
    for raw_action in project.blocked_actions:
        rules.append(
            PolicyRule(
                level=PolicyLevel.PROJECT,
                action=GovernedAction(raw_action),
                allowed=False,
                reason=f"Project policy blocks {raw_action} actions",
            )
        )

    return ExecutionContext(
        base_profile=base_profile,
        requested_profile=requested_profile,
        flow_authorized=flow_authorized,
        destructive_confirmed=destructive_confirmed,
        rules=tuple(rules),
    )
