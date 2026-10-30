"""Domain primitives for Factoria."""

from .contracts import Adapter, CheckRunner, MemoryStore, Plugin
from .fix import (
    ChangeScope,
    FindingSeverity,
    FixLimits,
    FixPhase,
    FixTask,
    ReproductionEvidence,
    ReproductionKind,
    ReviewFinding,
    ReviewResult,
    VerificationResult,
)
from .flow import Flow, FlowState, FlowStateMachine, InvalidTransitionError
from .models import CheckResult, PluginManifest, PluginType, ProjectMemory
from .permissions import PermissionDecision, PermissionPolicy, PermissionProfile

__all__ = [
    "Adapter",
    "ChangeScope",
    "CheckResult",
    "CheckRunner",
    "FindingSeverity",
    "FixLimits",
    "FixPhase",
    "FixTask",
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
    "ReproductionEvidence",
    "ReproductionKind",
    "ReviewFinding",
    "ReviewResult",
    "VerificationResult",
]
