from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class AgentRole(StrEnum):
    EXPLORER = "explorer"
    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    DOCUMENTER = "documenter"


class ModelProfile(StrEnum):
    RAPIDO = "rapido"
    EQUILIBRADO = "equilibrado"
    POTENTE = "potente"


class RoleAccess(StrEnum):
    READ_ONLY = "read_only"
    PROJECT_WRITE = "project_write"
    MEMORY_WRITE = "memory_write"


@dataclass(frozen=True, slots=True)
class RoleSpec:
    role: AgentRole
    default_profile: ModelProfile
    access: RoleAccess
    structured_output: bool = False


ROLE_SPECS: Mapping[AgentRole, RoleSpec] = MappingProxyType(
    {
        AgentRole.EXPLORER: RoleSpec(
            AgentRole.EXPLORER, ModelProfile.EQUILIBRADO, RoleAccess.READ_ONLY
        ),
        AgentRole.PLANNER: RoleSpec(
            AgentRole.PLANNER, ModelProfile.POTENTE, RoleAccess.READ_ONLY, structured_output=True
        ),
        AgentRole.IMPLEMENTER: RoleSpec(
            AgentRole.IMPLEMENTER, ModelProfile.POTENTE, RoleAccess.PROJECT_WRITE
        ),
        AgentRole.REVIEWER: RoleSpec(
            AgentRole.REVIEWER, ModelProfile.POTENTE, RoleAccess.READ_ONLY, structured_output=True
        ),
        AgentRole.DOCUMENTER: RoleSpec(
            AgentRole.DOCUMENTER, ModelProfile.EQUILIBRADO, RoleAccess.READ_ONLY
        ),
    }
)


@dataclass(frozen=True, slots=True, init=False)
class ModelRouter:
    models: Mapping[str, Mapping[ModelProfile, str]]
    strict: bool

    def __init__(
        self,
        models: Mapping[str, Mapping[ModelProfile, str]] | None = None,
        *,
        mapping: Mapping[str, Mapping[ModelProfile, str]] | None = None,
        strict: bool | None = None,
    ) -> None:
        if models is not None and mapping is not None:
            raise ValueError("Provide either models or mapping, not both")
        selected = mapping if mapping is not None else models
        normalized = {
            name: MappingProxyType(dict(profiles))
            for name, profiles in dict(selected or {}).items()
        }
        object.__setattr__(self, "models", MappingProxyType(normalized))
        # The `mapping=` form is used by the live environment router. Treat it as
        # strict unless explicitly overridden so live flows never fall through to
        # an agent tool's implicit/default model.
        object.__setattr__(self, "strict", (mapping is not None) if strict is None else strict)

    def resolve(self, adapter: str, profile: ModelProfile) -> str | None:
        mapping = self.models.get(adapter)
        if mapping is None:
            return None
        return mapping.get(profile)

    def require(self, adapter: str, profile: ModelProfile) -> str:
        model = self.resolve(adapter, profile)
        if model is None:
            raise ValueError(
                f"No concrete model configured for adapter={adapter!r}, profile={profile.value!r}"
            )
        return model


@dataclass(frozen=True, slots=True)
class AdapterSafetyPolicy:
    restricted_access: Mapping[str, frozenset[RoleAccess]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    denied_access: Mapping[str, frozenset[RoleAccess]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    role_args: Mapping[str, Mapping[AgentRole, tuple[str, ...]]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    role_environment: Mapping[str, Mapping[AgentRole, Mapping[str, str]]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def supports(self, adapter: str, access: RoleAccess) -> bool:
        if access in self.denied_access.get(adapter, frozenset()):
            return False
        if access is RoleAccess.PROJECT_WRITE:
            return True
        return access in self.restricted_access.get(adapter, frozenset())

    def args_for(self, adapter: str, role: AgentRole) -> tuple[str, ...]:
        mapping = self.role_args.get(adapter)
        return () if mapping is None else mapping.get(role, ())

    def environment_for(self, adapter: str, role: AgentRole) -> Mapping[str, str]:
        mapping = self.role_environment.get(adapter)
        return MappingProxyType({}) if mapping is None else mapping.get(role, MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 2
    escalate_profile: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")


@dataclass(frozen=True, slots=True)
class AgentStage:
    role: AgentRole
    prompt: str
    profile: ModelProfile | None = None
    preferred_tool: str | None = None
    structured_output: bool | None = None
    timeout_seconds: int = 1800

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("Agent stage prompt cannot be empty")
        if self.timeout_seconds < 1:
            raise ValueError("Agent stage timeout must be positive")


@dataclass(frozen=True, slots=True)
class AgentAttemptTrace:
    attempt: int
    role: AgentRole
    adapter: str
    profile: ModelProfile
    model: str | None
    fallback: bool
    passed: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AgentStageTrace:
    role: AgentRole
    attempts: tuple[AgentAttemptTrace, ...]

    @property
    def passed(self) -> bool:
        return bool(self.attempts) and self.attempts[-1].passed
