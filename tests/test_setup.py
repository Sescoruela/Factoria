from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.adapters.base import AgentRequest, AgentResult, ToolCapability
from factoria.adapters.capability_matrix import load_builtin_capability_matrix
from factoria.application.setup import SetupError, SetupService
from factoria.config.loader import load_global_config
from factoria.domain.models import CheckResult
from factoria.domain.permissions import PermissionProfile


class FakeAdapter:
    def __init__(self, name: str, *, available: bool = True, checks_pass: bool = True) -> None:
        self._name = name
        self._available = available
        self._checks_pass = checks_pass

    @property
    def name(self) -> str:
        return self._name

    @property
    def executable(self) -> str:
        return self._name

    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset(ToolCapability)

    def available(self) -> bool:
        return self._available

    def build_command(self, request: AgentRequest) -> tuple[str, ...]:
        return (self._name, request.prompt)

    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(adapter=self._name, command=self.build_command(request), returncode=0)

    def self_test(self):
        return (
            CheckResult(
                name=f"{self._name}:self-test",
                passed=self._checks_pass and self._available,
                required=True,
                details="ok" if self._checks_pass and self._available else "failed",
            ),
        )


class SetupTests(unittest.TestCase):
    def test_builtin_capability_matrix_matches_supported_tools(self) -> None:
        matrix = load_builtin_capability_matrix()
        self.assertGreaterEqual(matrix.version, 2)
        common = {
            ToolCapability.NON_INTERACTIVE,
            ToolCapability.STRUCTURED_OUTPUT,
            ToolCapability.MODEL_SELECTION,
            ToolCapability.PROJECT_DIRECTORY,
            ToolCapability.READ_ONLY_ENFORCEMENT,
        }
        self.assertEqual(matrix.capabilities_for("codex"), frozenset(common))
        self.assertEqual(
            matrix.capabilities_for("opencode"),
            frozenset(common | {ToolCapability.PROJECT_WRITE_ENFORCEMENT}),
        )

    def test_setup_selects_first_ready_tool_and_writes_managed_config(self) -> None:
        matrix = load_builtin_capability_matrix()
        service = SetupService(
            adapters=(
                FakeAdapter("codex", available=False),
                FakeAdapter("opencode", available=True),
            ),
            matrix=matrix,
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / ".factoria" / "config.toml"
            plan = service.propose(target, requested_profile=PermissionProfile.SAFE)
            self.assertTrue(plan.can_apply)
            self.assertEqual(plan.proposed.default_tool, "opencode")
            self.assertEqual(plan.proposed.default_profile, PermissionProfile.SAFE)
            written = service.apply(plan, confirmed=True)
            loaded = load_global_config(written)
            self.assertEqual(loaded.default_tool, "opencode")
            self.assertEqual(loaded.default_profile, PermissionProfile.SAFE)

    def test_unmanaged_existing_config_is_never_overwritten_automatically(self) -> None:
        matrix = load_builtin_capability_matrix()
        service = SetupService(adapters=(FakeAdapter("codex"),), matrix=matrix)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.toml"
            target.write_text('default_profile = "normal"\n', encoding="utf-8")
            plan = service.propose(target)
            self.assertFalse(plan.can_apply)
            with self.assertRaises(SetupError):
                service.apply(plan, confirmed=True)
            self.assertEqual(target.read_text(encoding="utf-8"), 'default_profile = "normal"\n')

    def test_requested_tool_must_pass_self_tests(self) -> None:
        matrix = load_builtin_capability_matrix()
        service = SetupService(
            adapters=(FakeAdapter("codex", available=True, checks_pass=False),),
            matrix=matrix,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SetupError):
                service.propose(Path(tmp) / "config.toml", requested_tool="codex")

    def test_apply_requires_explicit_confirmation(self) -> None:
        matrix = load_builtin_capability_matrix()
        service = SetupService(adapters=(FakeAdapter("codex"),), matrix=matrix)
        with tempfile.TemporaryDirectory() as tmp:
            plan = service.propose(Path(tmp) / "config.toml")
            with self.assertRaises(SetupError):
                service.apply(plan, confirmed=False)


if __name__ == "__main__":
    unittest.main()
