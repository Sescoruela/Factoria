from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factoria.adapters.base import AgentRequest
from factoria.adapters.codex import CodexAdapter
from factoria.application.agent_flow_runtime import (
    LiveAgentFlowError,
    LiveAgentFlowRunner,
    _model_router_from_environment,
    default_live_orchestrator,
)
from factoria.cli import build_parser
from factoria.orchestration import AgentRole, ModelProfile, RoleAccess


class LiveAgentFlowTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        self._git(root, "init", "-b", "main")
        self._git(root, "config", "user.email", "factoria@example.invalid")
        self._git(root, "config", "user.name", "Factoria Test")
        (root / "README.md").write_text("test\n", encoding="utf-8")
        self._git(root, "add", "README.md")
        self._git(root, "commit", "-m", "init")
        return temp, root

    def test_flow_never_starts_directly_on_main(self) -> None:
        temp, root = self._repo()
        self.addCleanup(temp.cleanup)
        runner = LiveAgentFlowRunner(None, None, None, None, None)  # type: ignore[arg-type]
        with self.assertRaises(LiveAgentFlowError):
            runner._prepare_branch(root, requested=None)

    def test_explicit_branch_is_created_from_main(self) -> None:
        temp, root = self._repo()
        self.addCleanup(temp.cleanup)
        runner = LiveAgentFlowRunner(None, None, None, None, None)  # type: ignore[arg-type]
        branch = runner._prepare_branch(root, requested="work/fix")
        self.assertEqual(branch, "work/fix")
        self.assertEqual(self._git(root, "branch", "--show-current"), "work/fix")

    def test_default_policy_keeps_codex_implementer_blocked(self) -> None:
        orchestrator = default_live_orchestrator()
        policy = orchestrator.safety_policy
        self.assertTrue(policy.supports("codex", RoleAccess.READ_ONLY))
        self.assertFalse(policy.supports("codex", RoleAccess.PROJECT_WRITE))
        self.assertTrue(policy.supports("opencode", RoleAccess.PROJECT_WRITE))
        environment = policy.environment_for("opencode", AgentRole.IMPLEMENTER)
        self.assertIn("OPENCODE_PERMISSION", environment)
        self.assertIn('"edit":"allow"', environment["OPENCODE_PERMISSION"])

    @patch.object(CodexAdapter, "_resolved_executable", return_value=None)
    def test_codex_places_sandbox_flags_before_exec(self, _discovery) -> None:
        command = CodexAdapter().build_command(
            AgentRequest(
                prompt="Inspect",
                project_root=Path("."),
                extra_args=("--sandbox", "read-only", "--ask-for-approval", "never"),
            )
        )
        self.assertEqual(command[:6], ("codex", "--sandbox", "read-only", "--ask-for-approval", "never", "exec"))

    def test_model_profiles_can_be_mapped_by_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {"FACTORIA_CODEX_POTENTE": "codex-power", "FACTORIA_OPENCODE_RAPIDO": "provider/fast"},
            clear=False,
        ):
            router = _model_router_from_environment()
        self.assertEqual(router.resolve("codex", ModelProfile.POTENTE), "codex-power")
        self.assertEqual(router.resolve("opencode", ModelProfile.RAPIDO), "provider/fast")

    def test_cli_exposes_agent_flow_governance_flags(self) -> None:
        parser = build_parser()
        start = parser.parse_args(["feature", "Nueva pantalla", "--branch", "feature/ui", "--tool", "opencode"])
        self.assertEqual(start.branch, "feature/ui")
        self.assertEqual(start.tool, "opencode")
        resume = parser.parse_args(["resume", "flow-1", "--approve-plan", "--approve-final"])
        self.assertTrue(resume.approve_plan)
        self.assertTrue(resume.approve_final)


if __name__ == "__main__":
    unittest.main()
