from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.adapters.base import AgentRequest, AgentResult, ToolCapability
from factoria.adapters.opencode import OpenCodeAdapter, opencode_read_only_config_content
from factoria.adapters.registry import AdapterRegistry
from factoria.domain.models import CheckResult
from factoria.orchestration import (
    AdapterSafetyPolicy,
    AgentOrchestrationError,
    AgentOrchestrator,
    AgentRole,
    AgentStage,
    ModelRouter,
    RoleAccess,
)


class _NoWriteSafetyAdapter:
    @property
    def name(self) -> str:
        return "fake"

    @property
    def executable(self) -> str:
        return "fake"

    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset(
            {
                ToolCapability.NON_INTERACTIVE,
                ToolCapability.PROJECT_DIRECTORY,
            }
        )

    def available(self) -> bool:
        return True

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        return ("fake", request.prompt)

    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(adapter="fake", command=self.build_command(request), returncode=0)

    def self_test(self):
        return (CheckResult(name="fake:self-test", passed=True, required=True),)


class AdapterBehaviorVerificationTests(unittest.TestCase):
    def test_project_write_role_requires_verified_write_enforcement(self) -> None:
        registry = AdapterRegistry()
        registry.register(_NoWriteSafetyAdapter())
        orchestrator = AgentOrchestrator(
            registry=registry,
            model_router=ModelRouter(),
            safety_policy=AdapterSafetyPolicy(),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AgentOrchestrationError):
                orchestrator.run(
                    AgentStage(AgentRole.IMPLEMENTER, "Implement"),
                    project_root=Path(tmp),
                )

    def test_opencode_translates_internal_permission_to_supported_inline_config(self) -> None:
        adapter = OpenCodeAdapter()
        permission = json.dumps({"*": "deny", "read": "allow"}, separators=(",", ":"))
        captured_environment: dict[str, str] = {}

        def fake_execute(request, command, *, adapter_name):
            captured_environment.update(request.environment)
            return AgentResult(adapter=adapter_name, command=command, returncode=0)

        with tempfile.TemporaryDirectory() as tmp, patch.object(
            OpenCodeAdapter, "_execute", side_effect=fake_execute
        ):
            result = adapter.run(
                AgentRequest(
                    prompt="Inspect",
                    project_root=Path(tmp),
                    environment={"OPENCODE_PERMISSION": permission},
                )
            )

        self.assertTrue(result.passed)
        self.assertNotIn("OPENCODE_PERMISSION", captured_environment)
        self.assertEqual(
            json.loads(captured_environment["OPENCODE_CONFIG_CONTENT"]),
            {"permission": {"*": "deny", "read": "allow"}},
        )

    def test_opencode_resolved_config_probe_requires_inline_policy_to_win(self) -> None:
        adapter = OpenCodeAdapter()
        expected_permission = json.loads(opencode_read_only_config_content())["permission"]
        completed = subprocess.CompletedProcess(
            args=["opencode", "debug", "config"],
            returncode=0,
            stdout=json.dumps({"permission": expected_permission}),
            stderr="",
        )
        with patch.object(OpenCodeAdapter, "available", return_value=True), patch(
            "factoria.adapters.opencode.subprocess.run", return_value=completed
        ) as run:
            check = adapter._resolved_permission_check(
                name="probe",
                config_content=opencode_read_only_config_content(),
                expected=expected_permission,
            )

        self.assertTrue(check.passed)
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["OPENCODE_CONFIG_CONTENT"], opencode_read_only_config_content())

    def test_opencode_resolved_config_probe_rejects_permission_override(self) -> None:
        adapter = OpenCodeAdapter()
        expected_permission = json.loads(opencode_read_only_config_content())["permission"]
        completed = subprocess.CompletedProcess(
            args=["opencode", "debug", "config"],
            returncode=0,
            stdout=json.dumps({"permission": {"*": "allow", "read": "allow"}}),
            stderr="",
        )
        with patch.object(OpenCodeAdapter, "available", return_value=True), patch(
            "factoria.adapters.opencode.subprocess.run", return_value=completed
        ):
            check = adapter._resolved_permission_check(
                name="probe",
                config_content=opencode_read_only_config_content(),
                expected=expected_permission,
            )

        self.assertFalse(check.passed)
        self.assertIn("permission mismatch", check.details or "")


if __name__ == "__main__":
    unittest.main()
