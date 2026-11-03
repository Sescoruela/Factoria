from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factoria.application.workflow_presets import (
    VisualWorkflowPreset,
    VisualWorkflowStep,
    default_preset,
    load_preset,
    save_preset,
    validate_preset,
)
from factoria.web_app import _apply_workflow_defaults


class VisualWorkflowPresetTests(unittest.TestCase):
    def test_feature_cannot_disable_required_step(self) -> None:
        base = default_preset("feature")
        steps = tuple(
            VisualWorkflowStep(
                name=step.name,
                role=step.role,
                profile=step.profile,
                tool=step.tool,
                enabled=False if step.name == "review" else step.enabled,
            )
            for step in base.steps
        )
        with self.assertRaisesRegex(ValueError, "obligatorias"):
            validate_preset(VisualWorkflowPreset(kind="feature", steps=steps))

    def test_unsafe_reorder_is_rejected(self) -> None:
        base = default_preset("feature")
        steps = list(base.steps)
        steps[2], steps[3] = steps[3], steps[2]
        with self.assertRaisesRegex(ValueError, "orden solicitado no es seguro"):
            validate_preset(VisualWorkflowPreset(kind="feature", steps=tuple(steps)))

    def test_multiple_explicit_agents_are_rejected_for_one_flow(self) -> None:
        base = default_preset("feature")
        steps = []
        for step in base.steps:
            tool = "codex" if step.name == "explore" else "opencode" if step.name == "implement" else None
            steps.append(
                VisualWorkflowStep(
                    name=step.name,
                    role=step.role,
                    profile=step.profile,
                    tool=tool,
                    enabled=step.enabled,
                )
            )
        with self.assertRaisesRegex(ValueError, "único agente explícito"):
            validate_preset(VisualWorkflowPreset(kind="feature", steps=tuple(steps)))

    def test_fix_optional_steps_persist_per_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = default_preset("fix")
            custom = VisualWorkflowPreset(
                kind="fix",
                steps=(
                    base.steps[0],
                    VisualWorkflowStep("plan", "planner", tool="codex", enabled=True),
                    VisualWorkflowStep("implement", "implementer", tool="codex", enabled=True),
                    VisualWorkflowStep("review", "reviewer", tool="codex", enabled=True),
                    VisualWorkflowStep("document", "documenter", tool="codex", enabled=True),
                ),
            )
            save_preset(root, custom)
            loaded = load_preset(root, "fix")
            self.assertEqual([step.name for step in loaded.steps], ["explore", "plan", "implement", "review", "document"])
            self.assertTrue(next(step for step in loaded.steps if step.name == "plan").enabled)
            self.assertEqual(next(step for step in loaded.steps if step.name == "review").tool, "codex")

    def test_fix_preset_changes_real_launch_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            preset = VisualWorkflowPreset(
                kind="fix",
                steps=(
                    VisualWorkflowStep("explore", "explorer", tool="opencode"),
                    VisualWorkflowStep("plan", "planner", tool="opencode", enabled=True),
                    VisualWorkflowStep("implement", "implementer", tool="opencode"),
                    VisualWorkflowStep("review", "reviewer", tool="opencode"),
                    VisualWorkflowStep("document", "documenter", tool="opencode", enabled=True),
                ),
            )
            save_preset(root, preset)
            args = _apply_workflow_defaults(["fix", "demo"], root)
            self.assertIn("--large", args)
            self.assertIn("--update-memory", args)
            tool_index = args.index("--tool")
            self.assertEqual(args[tool_index + 1], "opencode")


if __name__ == "__main__":
    unittest.main()
