from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from factoria.application.agent_flow_runtime import LiveAgentFlowRunner
from factoria.application.agent_profiles import AgentCatalogConflict, AgentRoleProfile, save_agent_profile
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.project_integration import ProjectIntegration, project_definition
from factoria.application.runtime_state import LiveFlowSession, RuntimeStage
from factoria.application.workflow_presets import (
    WorkflowCatalogConflict, default_preset, load_preset, preset_to_workflow, save_preset,
    validate_preset, workflow_catalog_revision, workflow_snapshot, workflow_from_snapshot,
)
from factoria.orchestration.models import AgentRole
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _workflow_payload


def assigned(kind='feature', stage='review', identifier='api-reviewer'):
    base = default_preset(kind)
    return replace(base, steps=tuple(replace(s, agent_id=identifier) if s.name == stage else s for s in base.steps))


class WorkflowAgentAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        home = patch('pathlib.Path.home', return_value=self.root / 'home')
        home.start()
        self.addCleanup(home.stop)
        (self.root / 'rules.md').write_text('Preserve the public API.', encoding='utf-8')
        self.agent = AgentRoleProfile('api-reviewer', 'rapido', 'opencode', 'Check HTTP compatibility.',
                                      ('rules.md',), 'reviewer', 'API reviewer')
        save_agent_profile(self.root, self.agent, mode='create')

    def test_assignment_persists_identity_and_inherits_preferences_without_changing_role(self):
        save_preset(self.root, assigned())
        loaded = load_preset(self.root, 'feature')
        step = next(s for s in preset_to_workflow(loaded, project_root=self.root).steps if s.name == 'review')
        self.assertEqual(step.agent_id, self.agent.role)
        self.assertEqual(step.role, AgentRole.REVIEWER)
        self.assertEqual(step.profile.value, 'rapido')
        self.assertEqual(step.preferred_tool, 'opencode')
        self.assertEqual(next(s for s in loaded.steps if s.name == 'review').agent_id, self.agent.role)

    def test_stage_overrides_have_priority_over_agent_preferences(self):
        preset = assigned()
        preset = replace(preset, steps=tuple(replace(s, profile='potente', tool='codex') if s.name == 'review' else s for s in preset.steps))
        step = next(s for s in preset_to_workflow(preset, project_root=self.root).steps if s.name == 'review')
        self.assertEqual(step.profile.value, 'potente')
        self.assertEqual(step.preferred_tool, 'codex')
        self.assertEqual(step.role, AgentRole.REVIEWER)

    def test_invalid_assignment_preserves_disk_including_disabled_stages(self):
        path = save_preset(self.root, default_preset('fix'))
        before = path.read_bytes()
        for preset in (assigned('fix', 'review', 'missing'), assigned('fix', 'implement'), assigned('fix', 'plan')):
            with self.subTest(preset=preset), self.assertRaises(ValueError):
                save_preset(self.root, preset)
            self.assertEqual(path.read_bytes(), before)
        # A manually edited source also fails at preparation, never falls back to the basic agent.
        data = json.loads(before)
        data['fix'] = assigned('fix', 'review', 'missing').to_mapping()
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError):
            ProjectIntegration(self.root).plan()

    def test_legacy_presets_and_snapshots_keep_basic_agents(self):
        preset = default_preset('fix')
        data = preset.to_mapping()
        for step in data['steps']:
            step.pop('agent_id', None)
        folder = self.root / '.factoria'
        (folder / 'ui-workflows.json').write_text(json.dumps({'fix': data}))
        loaded = load_preset(self.root, 'fix')
        self.assertTrue(all(s.agent_id is None for s in loaded.steps))
        workflow = preset_to_workflow(loaded, project_root=self.root)
        snapshot = workflow_snapshot(workflow)
        self.assertTrue(all('agent_id' not in s for s in snapshot))
        self.assertEqual(workflow_from_snapshot('fix', snapshot), workflow)

    def test_referenced_base_role_cannot_change_until_detached(self):
        save_preset(self.root, assigned())
        path = self.root / '.factoria/agents.json'
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'compatible'):
            save_agent_profile(self.root, replace(self.agent, base_role='implementer'))
        self.assertEqual(path.read_bytes(), before)
        save_preset(self.root, default_preset('feature'))
        save_agent_profile(self.root, replace(self.agent, base_role='implementer'))

    def test_new_assignment_during_agent_edit_prevents_incompatible_catalog_write(self):
        workflow_file = save_preset(self.root, default_preset('feature'))
        agent_file = self.root / '.factoria/agents.json'
        before = agent_file.read_bytes()
        real_fsync = os.fsync
        def assign_during_write(fd):
            real_fsync(fd)
            payload = json.loads(workflow_file.read_text(encoding='utf-8'))
            payload['feature'] = assigned().to_mapping()
            workflow_file.write_text(json.dumps(payload), encoding='utf-8')
        with patch('factoria.application.agent_profiles.os.fsync', side_effect=assign_during_write):
            with self.assertRaises(AgentCatalogConflict):
                save_agent_profile(self.root, replace(self.agent, base_role='implementer'))
        self.assertEqual(agent_file.read_bytes(), before)
        self.assertEqual(load_preset(self.root, 'feature').steps[3].agent_id, self.agent.role)

    def test_agent_edit_invalidates_workflow_draft_revision(self):
        revision = workflow_catalog_revision(self.root)
        save_agent_profile(self.root, replace(self.agent, instructions='New rules'))
        with self.assertRaises(WorkflowCatalogConflict):
            save_preset(self.root, assigned(), expected_revision=revision)
        self.assertFalse((self.root / '.factoria/workflows.json').exists())

    def test_snapshot_and_orchestrated_prompt_use_frozen_custom_agent(self):
        save_preset(self.root, assigned())
        workflow = preset_to_workflow(load_preset(self.root, 'feature'), project_root=self.root)
        session = LiveFlowSession(flow_id='fixture', kind='feature', title='Review API', branch='work/test',
                                  preferred_tool=None, runtime_stage=RuntimeStage.RUNNING,
                                  workflow_steps=workflow_snapshot(workflow), agent_profiles=tuple(project_definition(self.root)['agents']))
        restored = LiveFlowSession.from_mapping(session.to_mapping())
        runner = LiveAgentFlowRunner(None, None, FlowArtifactStore(self.root), None, None)  # type: ignore[arg-type]
        review = next(s for s in runner._workflow(restored).steps if s.name == 'review')
        save_agent_profile(self.root, replace(self.agent, instructions='Later agent instructions', profile='potente'))
        (self.root / 'rules.md').write_text('Later skill instructions', encoding='utf-8')
        memory = type('Memory', (), {'mandatory_rules': (), 'project_name': 'Fixture'})()
        prompt = runner._prompt(review, restored, memory)
        self.assertIn(self.agent.instructions, prompt)
        self.assertIn('Preserve the public API.', prompt)
        self.assertNotIn('Later agent instructions', prompt)
        self.assertIn('Return ONLY one JSON', prompt)
        self.assertEqual(review.agent_id, self.agent.role)
        self.assertEqual(review.role, AgentRole.REVIEWER)
        self.assertEqual(review.profile.value, 'rapido')

    def test_both_tool_guides_and_open_code_permissions_use_selected_agent(self):
        save_preset(self.root, assigned('fix'))
        plan = ProjectIntegration(self.root).plan()
        for name in ('.agents/skills/factoria-fix/SKILL.md', '.opencode/commands/factoria-fix.md'):
            guide = plan.files[name]
            self.assertIn('agente `api-reviewer`', guide)
            self.assertIn(self.agent.instructions, guide)
            self.assertIn('rules.md', guide)
            self.assertIn('perfil `rapido`', guide)
        self.assertNotIn('"edit": "ask"', plan.files['.opencode/agents/factoria-api-reviewer.md'])
        self.assertIn('"*": "deny"', plan.files['.opencode/agents/factoria-api-reviewer.md'])

    def test_agent_identifier_cannot_bypass_stage_controls(self):
        for value in (True, 1, '../escape', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_preset(assigned('feature', 'review', value))
        preset = assigned()
        with self.assertRaises(ValueError):
            validate_preset(replace(preset, steps=tuple(replace(s, enabled=False) if s.name == 'review' else s for s in preset.steps)))
        raw = workflow_snapshot(preset_to_workflow(default_preset('fix')))
        with self.assertRaises(ValueError):
            workflow_from_snapshot('fix', ({**raw[0], 'agent_id': '../escape'}, *raw[1:]))

    def test_authenticated_api_validates_assignment_and_returns_catalog_after_save(self):
        (self.root / '.git').mkdir()
        UiWorkspaceSettings(self.root.parent, self.root).save()
        server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaWebHandler)
        server.factoria_token = 'fixture-token'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(preset):
                payload = {**preset.to_mapping(), 'revision': workflow_catalog_revision(self.root), 'project_path': str(self.root)}
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_address[1]}/api/workflow/save',
                                             data=json.dumps(payload).encode(), headers={'X-Factoria-Token': 'fixture-token'})
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            with patch('factoria.web_app._state', side_effect=lambda: {'workflows': _workflow_payload(self.root)}):
                response = request(assigned())
                self.assertIn(self.agent.role, [a['role'] for a in response['state']['workflows']['feature']['agents']])
                before = (self.root / '.factoria/workflows.json').read_bytes()
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request(assigned('feature', 'implement'))
                self.assertEqual(caught.exception.code, 400)
                self.assertEqual((self.root / '.factoria/workflows.json').read_bytes(), before)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
