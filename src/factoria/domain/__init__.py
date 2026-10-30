"""Domain primitives for Factoria."""

from .contracts import Adapter, CheckRunner, MemoryStore, Plugin
from .flow import Flow, FlowState, FlowStateMachine, InvalidTransitionError
from .models import CheckResult, PluginManifest, PluginType, ProjectMemory
from .permissions import PermissionDecision, PermissionPolicy, PermissionProfile

__all__ = [
    "Adapter",
    "CheckResult",
    "CheckRunner",
    "Flow",
    "FlowState",
    "FlowStateMachine",
    "InvalidTransitionError",
    "MemoryStore",
    "PermissionDecision",
    "PermissionPolicy",
    "PermissionProfile",
    "Plugin",
    "PluginManifest",
    "PluginType",
    "ProjectMemory",
]
