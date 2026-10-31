"""Tool adapters for coding agents."""

from .base import AgentRequest, AgentResult, ToolAdapter, ToolCapability
from .codex import CodexAdapter
from .opencode import OpenCodeAdapter
from .registry import AdapterRegistry, AdapterSelectionError

__all__ = [
    "AdapterRegistry",
    "AdapterSelectionError",
    "AgentRequest",
    "AgentResult",
    "CodexAdapter",
    "OpenCodeAdapter",
    "ToolAdapter",
    "ToolCapability",
]
