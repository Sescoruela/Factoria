from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.adapters.base import AgentRequest, AgentResult, ToolCapability
from factoria.adapters.registry import AdapterRegistry
from factoria.domain.models import CheckResult
from factoria.orchestration.models import (
    AdapterSafetyPolicy,
    AgentRole,
    AgentStage,
    ModelProfile,
    ModelRouter,
)
from factoria.orchestration.orchestrator import AgentOrchestrationError, AgentOrchestrator


class FakeAdapter:
    def __init__(self, *, self_test_passes: bool = True) -> None:
        self.requests: list[AgentRequest] = []
        self.self_test_calls = 0
        self.self_test_passes = self_test_passes

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def executable(self) -> str:
        return "opencode"

    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset(ToolCapability)

    def available(self) -> bool:
        return True

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        return (self.executable, request.prompt)

    def run(self, request: AgentRequest) -> AgentResult:
        self.requests.append(request)
        return AgentResult(adapter=self.name, command=self.build_command(request), returncode=0)

    def self_test(self):
        self.self_test_calls += 1
        return (
            CheckResult(
                name="opencode:capabilities",
                passed=self.self_test_passes,
                required=True,
            ),
        )


class DeterministicModelRoutingTests(unittest.TestCase):
    def _orchestrator(self, adapter: FakeAdapter, router: ModelRouter) -> AgentOrchestrator:
        registry = AdapterRegistry()
        registry.register(adapter)
        return AgentOrchestrator(
            registry=registry,
            model_router=router,
            safety_policy=AdapterSafetyPolicy(),
        )

    def test_mapping_keyword_enables_strict_live_routing(self) -> None:
        router = ModelRouter(mapping={})
        self.assertTrue(router.strict)

    def test_strict_routing_rejects_missing_concrete_model(self) -> None:
        adapter = FakeAdapter()
        orchestrator = self._orchestrator(adapter, ModelRouter(mapping={}))
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(AgentOrchestrationError):
                orchestrator.run(
                    AgentStage(AgentRole.IMPLEMENTER, "Implement"),
                    project_root=Path(temp_dir),
                )
        self.assertEqual(adapter.requests, [])

    def test_strict_routing_passes_resolved_model_to_adapter(self) -> None:
        adapter = FakeAdapter()
        router = ModelRouter(
            mapping={"opencode": {ModelProfile.POTENTE: "approved-power-model"}}
        )
        orchestrator = self._orchestrator(adapter, router)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = orchestrator.run(
                AgentStage(AgentRole.IMPLEMENTER, "Implement"),
                project_root=Path(temp_dir),
            )
        self.assertTrue(result.trace.passed)
        self.assertEqual(adapter.requests[0].model, "approved-power-model")

    def test_failed_runtime_self_test_blocks_adapter(self) -> None:
        adapter = FakeAdapter(self_test_passes=False)
        router = ModelRouter(
            mapping={"opencode": {ModelProfile.POTENTE: "approved-power-model"}}
        )
        orchestrator = self._orchestrator(adapter, router)
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(AgentOrchestrationError):
                orchestrator.run(
                    AgentStage(AgentRole.IMPLEMENTER, "Implement"),
                    project_root=Path(temp_dir),
                )
        self.assertEqual(adapter.requests, [])

    def test_runtime_self_test_is_cached_per_orchestrator(self) -> None:
        adapter = FakeAdapter()
        router = ModelRouter(
            mapping={"opencode": {ModelProfile.POTENTE: "approved-power-model"}}
        )
        orchestrator = self._orchestrator(adapter, router)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            orchestrator.run(AgentStage(AgentRole.IMPLEMENTER, "First"), project_root=root)
            orchestrator.run(AgentStage(AgentRole.IMPLEMENTER, "Second"), project_root=root)
        self.assertEqual(adapter.self_test_calls, 1)


if __name__ == "__main__":
    unittest.main()
