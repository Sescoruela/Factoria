from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from factoria.application.agent_profiles import load_agent_profiles, save_agent_profile
from factoria.application.skill_catalog import SkillDefinition, save_skill
from factoria.application.agent_profiles import AgentRoleProfile
from factoria.application.project_integration import ProjectIntegration
from factoria.application.visual_agents import visual_agent_templates
from factoria.application.workflow_presets import default_preset, save_preset, validate_assignments
from factoria.web_editor_state import enrich_editor_state


class VisualAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        home = patch("pathlib.Path.home", return_value=self.root / "home")
        home.start()
        self.addCleanup(home.stop)

    def test_templates_are_opt_in_and_state_read_does_not_write(self):
        original = load_agent_profiles(self.root)
        payload = enrich_editor_state({"agents": []}, self.root)
        self.assertIn("integration-planner", {item["role"] for item in payload["agent_templates"]})
        self.assertEqual(load_agent_profiles(self.root), original)
        self.assertFalse(any(self.root.iterdir()))
        payload["agent_templates"][0]["instructions"] = "draft edit"
        self.assertNotEqual(visual_agent_templates()[0].instructions, "draft edit")

    def test_save_assign_and_export_visual_specialists_for_both_tools(self):
        templates = visual_agent_templates()
        for agent in templates:
            save_agent_profile(self.root, agent, mode="create")
        preset = default_preset("feature")
        roles = {a.base_role: a.role for a in templates}
        preset = replace(preset, steps=tuple(
            replace(s, agent_id=roles.get(s.role)) for s in preset.steps
        ))
        save_preset(self.root, preset)
        integration = ProjectIntegration(self.root)
        integration.apply(confirmed=True)
        self.assertTrue(integration.check()["ready"])
        for guide in (
            ".agents/skills/factoria-feature/SKILL.md",
            ".opencode/commands/factoria-feature.md",
            ".factoria/generated/chatgpt-context.md",
        ):
            content = (self.root / guide).read_text(encoding="utf-8")
            for agent in templates:
                self.assertIn(agent.instructions, content)
        for agent in templates:
            exported = (self.root / f".opencode/agents/factoria-{agent.role}.md").read_text()
            self.assertNotIn('"edit": "allow"', exported)
            self.assertNotIn('"edit": "ask"', exported)

    def test_product_designer_can_export_with_saved_flows_skill(self):
        state = enrich_editor_state({"agents": []}, self.root)
        skill = SkillDefinition.from_mapping(next(item for item in state["skill_templates"] if item["id"] == "product-flows"))
        save_skill(self.root, skill, expected_revision=state["skill_catalog_revision"], create=True)
        template = next(a for a in state["agent_templates"] if a["role"] == "product-designer")
        agent = replace(AgentRoleProfile.from_mapping(template), skills=(skill.path,))
        save_agent_profile(self.root, agent, mode="create")
        preset = default_preset("feature")
        save_preset(self.root, replace(preset, steps=tuple(
            replace(step, agent_id=agent.role) if step.name == "plan" else step
            for step in preset.steps
        )))
        integration = ProjectIntegration(self.root)
        integration.apply(confirmed=True)
        self.assertTrue(integration.check()["ready"])
        for guide in (".agents/skills/factoria-feature/SKILL.md", ".opencode/commands/factoria-feature.md"):
            content = (self.root / guide).read_text(encoding="utf-8")
            self.assertIn(agent.instructions, content)
            self.assertIn(f"Consultar `{skill.path}`", content)

    def test_integration_planner_and_diagnostics_export_to_workflow_guides(self):
        state = enrich_editor_state({"agents": []}, self.root)
        skill_ids = ("api-migration", "sql-diagnostics", "production-diagnostics")
        templates = {item["id"]: item for item in state["skill_templates"]}
        for identifier in skill_ids:
            skill = SkillDefinition.from_mapping(templates[identifier])
            save_skill(
                self.root, skill, expected_revision=state["skill_catalog_revision"], create=True
            )
            state = enrich_editor_state({"agents": []}, self.root)
        planner = next(a for a in state["agent_templates"] if a["role"] == "integration-planner")
        paths = tuple(templates[identifier]["path"] for identifier in skill_ids)
        save_agent_profile(
            self.root, replace(AgentRoleProfile.from_mapping(planner), skills=paths), mode="create"
        )
        preset = default_preset("feature")
        steps = tuple(
            replace(step, agent_id=planner["role"]) if step.name == "plan" else step
            for step in preset.steps
        )
        save_preset(self.root, replace(preset, steps=steps))

        integration = ProjectIntegration(self.root)
        integration.apply(confirmed=True)
        self.assertTrue(integration.check()["ready"])
        for guide in (
            ".agents/skills/factoria-feature/SKILL.md",
            ".opencode/commands/factoria-feature.md",
        ):
            content = (self.root / guide).read_text(encoding="utf-8")
            self.assertIn(planner["instructions"], content)
            for path in paths:
                self.assertIn(f"Consultar `{path}`", content)

    def test_wrong_stage_and_duplicate_cannot_overwrite_catalog(self):
        designer = visual_agent_templates()[0]
        path = save_agent_profile(self.root, designer, mode="create")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "existe"):
            save_agent_profile(self.root, replace(designer, instructions="replacement"), mode="create")
        self.assertEqual(path.read_bytes(), before)
        preset = default_preset("feature")
        invalid = replace(preset, steps=tuple(
            replace(s, agent_id=designer.role) if s.name == "implement" else s
            for s in preset.steps
        ))
        with self.assertRaisesRegex(ValueError, "compatible"):
            validate_assignments(invalid, load_agent_profiles(self.root))


if __name__ == "__main__":
    unittest.main()
