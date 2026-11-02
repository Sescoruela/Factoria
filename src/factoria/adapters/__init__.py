"""Tool adapters for coding agents."""

from .argument_policy import AdapterArgumentPolicy, ArgumentPolicyError
from .base import AgentRequest, AgentResult, ToolAdapter, ToolCapability, validate_adapter_args
from .codex import CodexAdapter
from .opencode import OpenCodeAdapter
from .registry import AdapterRegistry, AdapterSelectionError

__all__ = [
    "AdapterArgumentPolicy",
    "AdapterRegistry",
    "AdapterSelectionError",
    "AgentRequest",
    "AgentResult",
    "ArgumentPolicyError",
    "CodexAdapter",
    "OpenCodeAdapter",
    "ToolAdapter",
    "ToolCapability",
    "validate_adapter_args",
]
