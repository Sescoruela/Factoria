from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from factoria.adapters import AdapterArgumentPolicy
from factoria.adapters.base import AgentRequest, AgentResult, ToolCapability
from factoria.adapters.registry import AdapterRegistry
from factoria.orchestration import (
    AdapterSafetyPolicy,
    AgentOrchestrationError,
    AgentOrchestrator,
    AgentRole,
    AgentStage,
    AgentWorkflowPlanner,
    ModelProfile,
    ModelRouter,
    RetryPolicy,
    RoleAccess,
)


class FakeAdapter:
    def __init__(self, name: str, outcomes: list[bool]) -> None:
        self._name = name
        self.outcomes = list(outcomes)
        self.requests: list[AgentRequest] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def executable(self) -> str:
        return self._name

    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset(ToolCapability)

    def available(self) -> bool:
        return True

    def argument_policy(self) -> AdapterArgumentPolicy:
        return AdapterArgumentPolicy(
            allowed=MappingProxyType({"--read-only-policy": ()})
        )

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        return (self._name, request.prompt)

    def run(self, request: AgentRequest) -> AgentResult:
        self.requests.append(request)
        passed = self.outcomes.pop(0) if self.outcomes else True
        return AgentResult(
            adapter=self._name,
            command=self.build_command(request),
            returncode=0 if passed else 1,
            stdout="ok" if passed else "",
        )

    def self_test(self):
        return ()


class AgentOrchestratorTests(unittest.TestCase):
    def _root(self):
        return tempfile.TemporaryDirectory()

    def test_uses_abstract_profile_mapping(self) -> None:
        adapter = FakeAdapter("codex", [True])
        registry = AdapterRegistry()
        registry.register(adapter)
        router = ModelRouter(
            {"codex": {ModelProfile.POTENTE: "configured-power-model"}}
        )
        orchestrator = AgentOrchestrator(
            registry=registry,
            model_router=router,
            safety_policy=AdapterSafetyPolicy(),
        )
        with self._root() as tmp:
            result = orchestrator.run(
                AgentStage(AgentRole.IMPLEMENTER, "Implement the approved change"),
                project_root=Path(tmp),
            )
        self.assertTrue(result.trace.passed)
        self.assertEqual(adapter.requests[0].model, "configured-power-model")

    def test_failure_falls_back_and_escalates_profile(self) -> None:
        codex = FakeAdapter("codex", [False])
        opencode = FakeAdapter("opencode", [True])
        registry = AdapterRegistry()
        registry.register(codex)
        registry.register(opencode)
        router = ModelRouter(
            {
                "codex": {ModelProfile.RAPIDO: "codex-fast"},
                "opencode": {ModelProfile.EQUILIBRADO: "opencode-balanced"},
            }
        )
        orchestrator = AgentOrchestrator(
            registry=registry,
            model_router=router,
            safety_policy=AdapterSafetyPolicy(),
            retry_policy=RetryPolicy(max_attempts=2, escalate_profile=True),
        )
        with self._root() as tmp:
            result = orchestrator.run(
                AgentStage(
                    AgentRole.IMPLEMENTER,
                    "Implement",
                    profile=ModelProfile.RAPIDO,
                    preferred_tool="codex",
                ),
                project_root=Path(tmp),
            )
        self.assertTrue(result.trace.passed)
        self.assertEqual([item.adapter for item in result.trace.attempts], ["codex", "opencode"])
        self.assertEqual(result.trace.attempts[1].profile, ModelProfile.EQUILIBRADO)
        self.assertTrue(result.trace.attempts[1].fallback)
        self.assertEqual(opencode.requests[0].model, "opencode-balanced")

    def test_read_only_role_is_blocked_without_explicit_policy(self) -> None:
        registry = AdapterRegistry()
        registry.register(FakeAdapter("codex", [True]))
        orchestrator = AgentOrchestrator(
            registry=registry,
            model_router=ModelRouter(),
            safety_policy=AdapterSafetyPolicy(),
        )
        with self._root() as tmp:
            with self.assertRaises(AgentOrchestrationError):
                orchestrator.run(
                    AgentStage(AgentRole.EXPLORER, "Inspect only"),
                    project_root=Path(tmp),
                )

    def test_explicit_read_only_policy_enables_restricted_role(self) -> None:
        adapter = FakeAdapter("codex", [True])
        registry = AdapterRegistry()
        registry.register(adapter)
        safety = AdapterSafetyPolicy(
            restricted_access={"codex": frozenset({RoleAccess.READ_ONLY})},
            role_args={"codex": {AgentRole.EXPLORER: ("--read-only-policy",)}},
        )
        orchestrator = AgentOrchestrator(
            registry=registry,
            model_router=ModelRouter(),
            safety_policy=safety,
        )
        with self._root() as tmp:
            result = orchestrator.run(
                AgentStage(AgentRole.EXPLORER, "Inspect only"),
                project_root=Path(tmp),
            )
        self.assertTrue(result.trace.passed)
        self.assertEqual(adapter.requests[0].extra_args, ("--read-only-policy",))

    def test_flow_plans_match_fix_and_feature_governance(self) -> None:
        small_fix = AgentWorkflowPlanner.fix()
        large_fix = AgentWorkflowPlanner.fix(large=True, update_memory=True)
        feature = AgentWorkflowPlanner.feature()
        self.assertEqual(
            tuple(step.role for step in small_fix.steps),
            (AgentRole.EXPLORER, AgentRole.IMPLEMENTER, AgentRole.REVIEWER),
        )
        self.assertIn(AgentRole.PLANNER, tuple(step.role for step in large_fix.steps))
        self.assertEqual(feature.steps[-1].role, AgentRole.DOCUMENTER)


if __name__ == "__main__":
    unittest.main()
