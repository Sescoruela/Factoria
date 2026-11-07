from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable

from factoria.adapters import CodexAdapter, OpenCodeAdapter, ToolAdapter, ToolCapability
from factoria.adapters.capability_matrix import CapabilityMatrix, load_builtin_capability_matrix
from factoria.config.loader import load_global_config
from factoria.config.models import GlobalConfig
from factoria.domain.models import CheckResult
from factoria.domain.permissions import PermissionProfile


_GENERATED_MARKER = "# factoria: managed global config"


class SetupError(RuntimeError):
    """Raised when setup cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class ToolSetupStatus:
    name: str
    available: bool
    declared_capabilities: frozenset[ToolCapability]
    expected_capabilities: frozenset[ToolCapability]
    checks: tuple[CheckResult, ...]

    @property
    def matrix_compatible(self) -> bool:
        return self.expected_capabilities.issubset(self.declared_capabilities)

    @property
    def passed(self) -> bool:
        return (
            self.available
            and self.matrix_compatible
            and all(check.passed or not check.required for check in self.checks)
        )


@dataclass(frozen=True, slots=True)
class SetupPlan:
    target_path: Path
    current: GlobalConfig
    proposed: GlobalConfig
    tools: tuple[ToolSetupStatus, ...]
    python_version: str
    python_supported: bool
    can_apply: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def changed(self) -> bool:
        return self.current != self.proposed


@dataclass(frozen=True, slots=True)
class SetupService:
    adapters: tuple[ToolAdapter, ...] = field(
        default_factory=lambda: (CodexAdapter(), OpenCodeAdapter())
    )
    matrix: CapabilityMatrix = field(default_factory=load_builtin_capability_matrix)

    def save_tool_preference(self, target_path: Path, tool: str) -> Path:
        """Persist a preference without installation probes, login or CLI startup."""
        if tool not in {"codex", "opencode"}:
            raise SetupError("Unknown tool preference")
        target = target_path.expanduser().resolve()
        if target.exists() and not _is_managed(target):
            raise SetupError("Existing global config is not managed by Factoria")
        current = load_global_config(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            render_global_config(replace(current, default_tool=tool)), encoding="utf-8", newline=""
        )
        return target

    def inspect_tools(self) -> tuple[ToolSetupStatus, ...]:
        result: list[ToolSetupStatus] = []
        for adapter in self.adapters:
            declared = adapter.capabilities()
            expected = self.matrix.capabilities_for(adapter.name)
            checks = tuple(adapter.self_test())
            result.append(
                ToolSetupStatus(
                    name=adapter.name,
                    available=adapter.available(),
                    declared_capabilities=declared,
                    expected_capabilities=expected,
                    checks=checks,
                )
            )
        return tuple(result)

    def propose(
        self,
        target_path: Path,
        *,
        requested_tool: str | None = None,
        requested_profile: PermissionProfile | None = None,
    ) -> SetupPlan:
        target = target_path.expanduser().resolve()
        current = load_global_config(target)
        tools = self.inspect_tools()
        by_name = {item.name: item for item in tools}
        warnings: list[str] = []

        for item in tools:
            if item.available and not item.matrix_compatible:
                warnings.append(
                    f"{item.name}: adapter capabilities do not satisfy matrix v{self.matrix.version}"
                )
            failed = tuple(
                check.name for check in item.checks if check.required and not check.passed
            )
            if item.available and failed:
                warnings.append(f"{item.name}: self-test failed ({', '.join(failed)})")

        if requested_tool is not None:
            status = by_name.get(requested_tool)
            if status is None:
                raise SetupError(f"Unknown tool: {requested_tool}")
            if not status.passed:
                raise SetupError(
                    f"Requested default tool {requested_tool!r} is not ready; review its self-tests"
                )
            selected_tool = requested_tool
        else:
            selected_tool = current.default_tool
            if selected_tool is not None:
                current_status = by_name.get(selected_tool)
                if current_status is None or not current_status.passed:
                    warnings.append(
                        f"Configured default tool {selected_tool!r} is not currently ready"
                    )
                    selected_tool = None
            if selected_tool is None:
                selected_tool = next((item.name for item in tools if item.passed), None)

        proposed = GlobalConfig(
            default_profile=requested_profile or current.default_profile,
            default_tool=selected_tool,
            max_agents=current.max_agents,
            personal_plugin_paths=current.personal_plugin_paths,
            organization_plugin_paths=current.organization_plugin_paths,
        )

        managed = not target.exists() or _is_managed(target)
        if target.exists() and not managed:
            warnings.append(
                "Existing global config is not managed by Factoria; setup will not overwrite it automatically"
            )

        python_supported = sys.version_info >= (3, 11)
        if not python_supported:
            warnings.append("Factoria currently requires Python >= 3.11")
        if not any(item.passed for item in tools):
            warnings.append("No coding-agent tool passed the installation self-tests")

        return SetupPlan(
            target_path=target,
            current=current,
            proposed=proposed,
            tools=tools,
            python_version=".".join(str(item) for item in sys.version_info[:3]),
            python_supported=python_supported,
            can_apply=managed and python_supported,
            warnings=tuple(warnings),
        )

    def apply(self, plan: SetupPlan, *, confirmed: bool) -> Path:
        if not confirmed:
            raise SetupError(
                "Explicit confirmation is required before writing global configuration"
            )
        if not plan.can_apply:
            raise SetupError("Setup plan is not safe to apply automatically")
        plan.target_path.parent.mkdir(parents=True, exist_ok=True)
        plan.target_path.write_text(
            render_global_config(plan.proposed), encoding="utf-8", newline=""
        )
        return plan.target_path


def render_global_config(config: GlobalConfig) -> str:
    lines = [
        _GENERATED_MARKER,
        f"default_profile = {json.dumps(config.default_profile.value)}",
        f"max_agents = {config.max_agents}",
    ]
    if config.default_tool is not None:
        lines.insert(2, f"default_tool = {json.dumps(config.default_tool)}")
    lines.extend(
        [
            "",
            "[plugins]",
            "personal_paths = " + _toml_array(str(path) for path in config.personal_plugin_paths),
            "organization_paths = "
            + _toml_array(str(path) for path in config.organization_plugin_paths),
            "",
        ]
    )
    return "\n".join(lines)


def _toml_array(values: Iterable[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def _is_managed(path: Path) -> bool:
    try:
        first_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
    except OSError:
        return False
    return _GENERATED_MARKER in first_lines
