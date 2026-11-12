from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from factoria.application.agent_profiles import AgentRoleProfile, save_agent_profile
from factoria.application.project_integration import ProjectIntegration
from factoria.application.workflow_presets import (
    WorkflowCatalogConflict, default_preset, load_catalog, load_preset, save_preset, workflow_catalog_revision,
)
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler, _workflow_payload


def named(identifier='fix-api', kind='fix', name='Corrección de API'):
    return replace(default_preset(kind), id=identifier, name=name, description='Mantener compatibilidad HTTP')


class NamedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        home = patch('pathlib.Path.home', return_value=self.root / 'home')
        home.start()
        self.addCleanup(home.stop)

    def test_create_edit_reopen_and_basic_save_preserve_entire_catalog(self):
        first = named()
        second = named('feature-api', 'feature', 'Nueva API')
        save_preset(self.root, first, create=True)
        save_preset(self.root, second, create=True)
        self.assertEqual(load_preset(self.root, first.id), first)
        edited = replace(first, name='Revisión HTTP', description='Nuevo alcance')
        save_preset(self.root, edited, expected_revision=workflow_catalog_revision(self.root))
        save_preset(self.root, default_preset('fix'))
        catalog = load_catalog(self.root)
        self.assertEqual(set(catalog), {'fix', 'feature', first.id, second.id})
        self.assertEqual(catalog[first.id], edited)
        self.assertEqual(catalog[second.id], second)

    def test_duplicate_missing_and_base_type_changes_preserve_source(self):
        path = save_preset(self.root, named(), create=True)
        before = path.read_bytes()
        for preset, create in ((named(), True), (named('missing'), False), (named(kind='feature'), False)):
            with self.subTest(preset=preset), self.assertRaises(ValueError):
                save_preset(self.root, preset, create=create)
            self.assertEqual(path.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'no existe'):
            load_preset(self.root, 'unknown-workflow')

    def test_portable_ids_cannot_collide_with_generated_catalogs_or_escape(self):
        for identifier in ('../escape', '/outside', 'C:/outside', 'BadCase', 'fix', 'feature', 'agents', 'skills', 'workflows', 'chatgpt-context', 'nul', 'con', 'x' * 49, ''):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                save_preset(self.root, named(identifier), create=True)
        self.assertFalse((self.root / '.factoria/workflows.json').exists())

    def test_named_feature_cannot_remove_plan_review_or_change_role_order(self):
        preset = named('feature-api', 'feature')
        for stage in ('plan', 'review', 'implement', 'document'):
            invalid = replace(preset, steps=tuple(replace(s, enabled=False) if s.name == stage else s for s in preset.steps))
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                save_preset(self.root, invalid, create=True)
        invalid = replace(preset, steps=tuple(replace(s, agent_id='missing') if s.name == 'review' else s for s in preset.steps))
        with self.assertRaises(ValueError):
            save_preset(self.root, invalid, create=True)
        reordered = list(preset.steps)
        reordered[2], reordered[3] = reordered[3], reordered[2]
        with self.assertRaises(ValueError):
            save_preset(self.root, replace(preset, steps=tuple(reordered)), create=True)

    def test_named_metadata_secrets_are_not_written(self):
        with self.assertRaisesRegex(ValueError, 'secreto'):
            save_preset(self.root, replace(named(), description='password = "synthetic-example-secret"'), create=True)
        self.assertFalse((self.root / '.factoria/workflows.json').exists())

    def test_manually_injected_secret_is_blocked_even_when_named_flow_is_disabled(self):
        path = save_preset(self.root, named(), create=True)
        payload = json.loads(path.read_text(encoding='utf-8'))
        payload['fix-api']['description'] = 'password = "synthetic-example-secret"'
        path.write_text(json.dumps(payload), encoding='utf-8')
        (self.root / '.factoria/config.toml').write_text('[flows]\nblocked=["fix-api"]\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'secreto'):
            ProjectIntegration(self.root).apply(confirmed=True)
        self.assertFalse((self.root / '.factoria/generated/workflows.md').exists())

    def test_named_edits_detect_stale_revision_without_losing_other_flows(self):
        path = save_preset(self.root, named(), create=True)
        stale = workflow_catalog_revision(self.root)
        save_preset(self.root, named('other-fix'), create=True)
        before = path.read_bytes()
        with self.assertRaises(WorkflowCatalogConflict):
            save_preset(self.root, replace(named(), name='Stale edit'), expected_revision=stale)
        self.assertEqual(before, path.read_bytes())
        self.assertIn('other-fix', load_catalog(self.root))

    def test_legacy_catalog_migration_keeps_named_and_basic_resources(self):
        folder = self.root / '.factoria'
        folder.mkdir()
        legacy = {'fix': default_preset('fix').to_mapping(), 'fix-api': named().to_mapping()}
        (folder / 'ui-workflows.json').write_text(json.dumps(legacy), encoding='utf-8')
        save_preset(self.root, default_preset('feature'))
        self.assertEqual(load_preset(self.root, 'fix-api'), named())
        self.assertTrue((folder / 'ui-workflows.json').exists())
        self.assertEqual(len(load_catalog(self.root)), 3)

    def test_agents_referenced_only_by_named_workflow_cannot_change_base_role(self):
        agent = AgentRoleProfile('api-reviewer', 'potente', base_role='reviewer', name='API reviewer')
        save_agent_profile(self.root, agent, mode='create')
        preset = named()
        preset = replace(preset, steps=tuple(replace(s, agent_id=agent.role) if s.name == 'review' else s for s in preset.steps))
        save_preset(self.root, preset, create=True)
        before = (self.root / '.factoria/agents.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'compatible'):
            save_agent_profile(self.root, replace(agent, base_role='implementer'))
        self.assertEqual(before, (self.root / '.factoria/agents.json').read_bytes())

    def test_named_exports_are_explicit_idempotent_and_conservative(self):
        save_preset(self.root, named(), create=True)
        save_preset(self.root, named('feature-api', 'feature'), create=True)
        plan = ProjectIntegration(self.root).plan()
        for path in ('.agents/skills/factoria-fix-api/SKILL.md', '.opencode/commands/factoria-fix-api.md'):
            self.assertIn('factoria native --compact start fix-api --tool', plan.files[path])
            self.assertIn('Tipo base: fix', plan.files[path])
        context_path = '.factoria/generated/policies/context-economy.md'
        self.assertIn('Presupuesto de contexto por etapa', plan.files[context_path])
        for identifier in ('fix', 'feature', 'fix-api', 'feature-api'):
            for path in (
                f'.agents/skills/factoria-{identifier}/SKILL.md',
                f'.opencode/commands/factoria-{identifier}.md',
            ):
                self.assertIn(context_path, plan.files[path])
                self.assertIn(f'factoria native --compact start {identifier} --tool', plan.files[path])
        bundle = plan.files['.factoria/generated/chatgpt-context.md']
        self.assertEqual(bundle.count(plan.files[context_path]), 1)
        self.assertIn('fix-api', plan.files['.factoria/generated/workflows.md'])
        self.assertIn('ambigua', plan.files['AGENTS.md'])
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        target = self.root / '.agents/skills/factoria-fix-api/SKILL.md'
        target.write_text('User edits', encoding='utf-8')
        save_preset(self.root, replace(named(), description='New scope'))
        with self.assertRaisesRegex(ValueError, 'modificados'):
            ProjectIntegration(self.root).apply(confirmed=True)
        self.assertEqual(target.read_text(), 'User edits')

    def test_blocking_named_id_keeps_builtin_but_blocking_base_removes_all_variants(self):
        save_preset(self.root, named(), create=True)
        service = ProjectIntegration(self.root)
        service.apply(confirmed=True)
        config = self.root / '.factoria/config.toml'
        config.write_text('[flows]\nblocked=["fix-api"]\n', encoding='utf-8')
        service.apply(confirmed=True)
        self.assertFalse((self.root / '.agents/skills/factoria-fix-api/SKILL.md').exists())
        self.assertTrue((self.root / '.agents/skills/factoria-fix/SKILL.md').exists())
        config.write_text('[flows]\nblocked=["fix"]\nallowed=["fix-api"]\n', encoding='utf-8')
        self.assertNotIn('.agents/skills/factoria-fix-api/SKILL.md', service.plan().files)
        self.assertEqual(len(load_catalog(self.root)), 3)

    def test_api_create_update_auth_conflicts_and_catalog_asset(self):
        (self.root / '.git').mkdir()
        UiWorkspaceSettings(self.root.parent, self.root).save()
        server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaWebHandler)
        server.factoria_token = 'test-token'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_address[1]}'
        try:
            def request(endpoint, payload, authorized=True):
                headers = {'Content-Type': 'application/json'}
                if authorized:
                    headers['X-Factoria-Token'] = 'test-token'
                req = urllib.request.Request(base + endpoint, data=json.dumps(payload).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            with urllib.request.urlopen(base + '/assets/workflows.js', timeout=3) as response:
                self.assertIn(b'newWorkflow', response.read())
            payload = {**named().to_mapping(), 'project_path': str(self.root), 'revision': workflow_catalog_revision(self.root)}
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request('/api/workflow/create', payload, False)
            self.assertEqual(caught.exception.code, 403)
            with patch('factoria.web_app._state', side_effect=lambda: {'workflows': _workflow_payload(self.root)}):
                result = request('/api/workflow/create', payload)
                self.assertIn('fix-api', result['state']['workflows'])
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/workflow/save', payload)
                self.assertEqual(caught.exception.code, 409)
                payload['revision'] = workflow_catalog_revision(self.root)
                payload['name'] = 'Revisión HTTP'
                result = request('/api/workflow/save', payload)
                self.assertEqual(result['state']['workflows']['fix-api']['name'], 'Revisión HTTP')
                before = (self.root / '.factoria/workflows.json').read_bytes()
                payload['revision'] = workflow_catalog_revision(self.root)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/workflow/create', payload)
                self.assertEqual(caught.exception.code, 400)
                self.assertEqual(before, (self.root / '.factoria/workflows.json').read_bytes())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
