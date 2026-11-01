from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .base import ToolCapability


class CapabilityMatrixError(ValueError):
    """Raised when the bundled capability matrix is invalid."""


@dataclass(frozen=True, slots=True)
class CapabilityMatrix:
    version: int
    tools: Mapping[str, frozenset[ToolCapability]]

    def capabilities_for(self, tool: str) -> frozenset[ToolCapability]:
        return self.tools.get(tool, frozenset())


def load_capability_matrix(path: Path) -> CapabilityMatrix:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CapabilityMatrixError("Capability matrix version must be a positive integer")
    raw_tools = data.get("tools", {})
    if not isinstance(raw_tools, dict):
        raise CapabilityMatrixError("Capability matrix [tools] must be a table")

    tools: dict[str, frozenset[ToolCapability]] = {}
    for name, raw in raw_tools.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            raise CapabilityMatrixError("Each tool capability entry must be a table")
        values = raw.get("capabilities", [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise CapabilityMatrixError(f"tools.{name}.capabilities must be a list of strings")
        try:
            capabilities = frozenset(ToolCapability(item) for item in values)
        except ValueError as exc:
            raise CapabilityMatrixError(f"Unknown capability in tools.{name}") from exc
        tools[name] = capabilities

    return CapabilityMatrix(version=version, tools=MappingProxyType(tools))


def load_builtin_capability_matrix() -> CapabilityMatrix:
    return load_capability_matrix(Path(__file__).with_name("capabilities.toml"))
