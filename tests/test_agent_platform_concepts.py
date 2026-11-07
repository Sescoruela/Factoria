from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.application.agent_flow_runtime import LiveAgentFlowRunner
from factoria.application.agent_profiles import (
    AgentRoleProfile,
    load_agent_profiles,
    save_agent_profile,
)
from factoria.application.runtime_state import LiveFlowSession, RuntimeStage
from factoria.application.workflow_presets import (
    VisualWorkflowPreset,
    VisualWorkflowStep,
    preset_to_workflow,
    workflow_snapshot,
)
from importlib.resources import files
UI_PATCH = files("factoria.web").joinpath("agents.js").read_text(encoding="utf-8")


class AgentPlatformConceptTests(unittest.TestCase):
    def test_agent_profile_persists_profile_and_platform(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_agent_profile(root, AgentRoleProfile("reviewer", "potente", "codex"))
            reviewer = next(item for item in load_agent_profiles(root) if item.role == "reviewer")
            self.assertEqual(reviewer.profile, "potente")
            self.assertEqual(reviewer.platform, "codex")

    def test_workflow_can_use_different_platforms_per_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save_agent_profile(root, AgentRoleProfile("explorer", "equilibrado", "codex"))
            save_agent_profile(root, AgentRoleProfile("implementer", "potente", "opencode"))
            preset = VisualWorkflowPreset(
                kind="fix",
                steps=(
                    VisualWorkflowStep("explore", "explorer", enabled=True),
                    VisualWorkflowStep("plan", "planner", enabled=False),
                    VisualWorkflowStep("implement", "implementer", enabled=True),
                    VisualWorkflowStep("review", "reviewer", enabled=True),
                    VisualWorkflowStep("document", "documenter", enabled=False),
                ),
            )
            workflow = preset_to_workflow(preset, project_root=root)
            platforms = {step.role.value: step.preferred_tool for step in workflow.steps}
            self.assertEqual(platforms["explorer"], "codex")
            self.assertEqual(platforms["implementer"], "opencode")

    def test_runtime_uses_frozen_workflow_snapshot(self) -> None:
        preset = VisualWorkflowPreset(
            kind="fix",
            steps=(
                VisualWorkflowStep("explore", "explorer", profile="rapido", tool="codex"),
                VisualWorkflowStep("implement", "implementer", profile="potente", tool="opencode"),
                VisualWorkflowStep("review", "reviewer", profile="potente", tool="codex"),
            ),
        )
        workflow = preset_to_workflow(preset)
        session = LiveFlowSession(
            flow_id="flow-1",
            kind="fix",
            title="demo",
            branch="feature/demo",
            preferred_tool=None,
            runtime_stage=RuntimeStage.RUNNING,
            workflow_steps=workflow_snapshot(workflow),
        )
        runner = LiveAgentFlowRunner(None, None, None, None, None)  # type: ignore[arg-type]
        restored = runner._workflow(session)
        self.assertEqual([step.preferred_tool for step in restored.steps], ["codex", "opencode", "codex"])
        self.assertEqual([step.profile.value for step in restored.steps], ["rapido", "potente", "potente"])

    def test_web_patch_separates_platforms_and_agents(self) -> None:
        self.assertIn("Plataformas", UI_PATCH)
        self.assertIn("Agentes de Factoria", UI_PATCH)
        self.assertIn("Plataforma preferida", UI_PATCH)
        self.assertIn("conserva una snapshot propia", UI_PATCH)


if __name__ == "__main__":
    unittest.main()
