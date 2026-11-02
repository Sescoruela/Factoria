from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from factoria.adapters.base import (
    AgentRequest,
    AgentResult,
    ArgumentPolicyError,
    ToolCapability,
    validate_adapter_args,
)
from factoria.adapters.registry import AdapterRegistry

from .models import (
    AdapterSafetyPolicy,
    AgentAttemptTrace,
    AgentRole,
    AgentStage,
    AgentStageTrace,
    ModelProfile,
    ModelRouter,
    ROLE_SPECS,
    RetryPolicy,
    RoleAccess,
)
from .runtime_validation import AdapterRuntimeValidator


class AgentOrchestrationError(RuntimeError):
    """Raised when no safe compatible agent execution path is available."""


@dataclass(frozen=True, slots=True)
class AgentStageResult:
    result: AgentResult
    trace: AgentStageTrace


@dataclass(frozen=True, slots=True)
class AgentOrchestrator:
    registry: AdapterRegistry
    model_router: ModelRouter
    safety_policy: AdapterSafetyPolicy
    retry_policy: RetryPolicy = RetryPolicy()
    runtime_validator: AdapterRuntimeValidator = field(default_factory=AdapterRuntimeValidator)

    def run(self, stage: AgentStage, *, project_root: Path) -> AgentStageResult:
        spec = ROLE_SPECS[stage.role]
        base_profile = stage.profile or spec.default_profile
        structured = spec.structured_output if stage.structured_output is None else stage.structured_output

        traces: list[AgentAttemptTrace] = []
        last_result: AgentResult | None = None
        used_adapters: list[str] = []

        for attempt in range(1, self.retry_policy.max_attempts + 1):
            profile = self._profile_for_attempt(base_profile, attempt)
            adapter, model, validated_args = self._select_adapter(
                role=stage.role,
                profile=profile,
                preferred=stage.preferred_tool,
                structured=structured,
                used_adapters=tuple(used_adapters),
            )
            used_adapters.append(adapter.name)

            request = AgentRequest(
                prompt=stage.prompt,
                project_root=project_root,
                model=model,
                structured_output=structured,
                timeout_seconds=stage.timeout_seconds,
                extra_args=validated_args,
                environment=self.safety_policy.environment_for(adapter.name, stage.role),
            )
            result = adapter.run(request)
            last_result = result
            traces.append(
                AgentAttemptTrace(
                    attempt=attempt,
                    role=stage.role,
                    adapter=adapter.name,
                    profile=profile,
                    model=model,
                    fallback=stage.preferred_tool is not None and adapter.name != stage.preferred_tool,
                    passed=result.passed,
                    error=result.error,
                )
            )
            if result.passed:
                return AgentStageResult(result=result, trace=AgentStageTrace(stage.role, tuple(traces)))

        if last_result is None:
            raise AgentOrchestrationError("No agent attempt was executed")
        return AgentStageResult(result=last_result, trace=AgentStageTrace(stage.role, tuple(traces)))

    def _select_adapter(
        self,
        *,
        role: AgentRole,
        profile: ModelProfile,
        preferred: str | None,
        structured: bool,
        used_adapters: tuple[str, ...],
    ):
        spec = ROLE_SPECS[role]
        names: list[str] = []
        if preferred is not None:
            names.append(preferred)
        names.extend(name for name in self.registry.adapters if name != preferred)

        candidates = []
        policy_rejections: list[str] = []
        for name in names:
            adapter = self.registry.adapters.get(name)
            if adapter is None or not adapter.available():
                continue
            if not self.safety_policy.supports(name, spec.access):
                continue

            model = self.model_router.resolve(name, profile)
            if self.model_router.strict and model is None:
                continue

            required = {
                ToolCapability.NON_INTERACTIVE,
                ToolCapability.PROJECT_DIRECTORY,
            }
            if spec.access is RoleAccess.READ_ONLY:
                required.add(ToolCapability.READ_ONLY_ENFORCEMENT)
            elif spec.access in {RoleAccess.PROJECT_WRITE, RoleAccess.MEMORY_WRITE}:
                required.add(ToolCapability.PROJECT_WRITE_ENFORCEMENT)
            if structured:
                required.add(ToolCapability.STRUCTURED_OUTPUT)
            if model is not None or self.model_router.strict:
                required.add(ToolCapability.MODEL_SELECTION)
            if not self.runtime_validator.supports(adapter, frozenset(required)):
                continue

            raw_args = self.safety_policy.args_for(name, role)
            try:
                validated_args = validate_adapter_args(adapter, raw_args)
            except ArgumentPolicyError as exc:
                policy_rejections.append(f"{name}: {exc}")
                continue
            candidates.append((adapter, model, validated_args))

        if not candidates:
            mapping_hint = " and an explicit model mapping" if self.model_router.strict else ""
            policy_hint = (
                "; argument policy rejected: " + " | ".join(policy_rejections)
                if policy_rejections
                else ""
            )
            raise AgentOrchestrationError(
                f"No safe verified adapter available for role={role.value}, profile={profile.value}{mapping_hint}{policy_hint}"
            )

        for adapter, model, validated_args in candidates:
            if adapter.name not in used_adapters:
                return adapter, model, validated_args
        return candidates[0]

    def _profile_for_attempt(self, base: ModelProfile, attempt: int) -> ModelProfile:
        if not self.retry_policy.escalate_profile or attempt <= 1:
            return base
        order = [ModelProfile.RAPIDO, ModelProfile.EQUILIBRADO, ModelProfile.POTENTE]
        index = order.index(base)
        return order[min(index + attempt - 1, len(order) - 1)]
