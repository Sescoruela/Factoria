from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from factoria.application.agent_profiles import (
    AgentCatalogConflict, AgentRoleProfile, agent_catalog_revision,
    agent_catalog_snapshot, load_agent_profiles, save_agent_profile,
)
from factoria.application.project_integration import ProjectIntegration
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer
from factoria.web_app_n8n import FactoriaN8NHandler


class AgentCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        home_patch = patch('pathlib.Path.home', return_value=self.root / 'home')
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.agent = AgentRoleProfile('revisor-api', 'potente', 'codex', 'Comprueba contratos de API.',
                                      base_role='reviewer', name='Revisor de API', description='Compatibilidad de contratos')

    def test_create_edit_reopen_and_export_custom_agent_without_changing_defaults(self) -> None:
        (self.root / 'rules.md').write_text('Mantener compatibilidad.', encoding='utf-8')
        original = load_agent_profiles(self.root)
        revision = agent_catalog_revision(self.root)
        save_agent_profile(self.root, replace(self.agent, skills=('rules.md',)), mode='create', expected_revision=revision)
        saved, revision = agent_catalog_snapshot(self.root)
        self.assertEqual(saved[:5], original)
        self.assertEqual(saved[-1].skills, ('rules.md',))
        updated = replace(saved[-1], name='Revisor HTTP', instructions='Comprueba códigos y contratos.', platform='opencode')
        save_agent_profile(self.root, updated, mode='update', expected_revision=revision)
        self.assertEqual(load_agent_profiles(self.root)[-1], updated)
        plan = ProjectIntegration(self.root).plan()
        self.assertIn(updated.instructions, plan.files['.opencode/agents/factoria-revisor-api.md'])
        self.assertIn(updated.instructions, plan.files['.factoria/generated/agents.md'])
        self.assertIn(updated.name, plan.files['.factoria/generated/chatgpt-context.md'])
        self.assertIn('agents.md', plan.files['AGENTS.md'])
        self.assertIn('"edit": "ask"', plan.files['.opencode/agents/factoria-implementer.md'])
        self.assertNotIn('"edit": "ask"', plan.files['.opencode/agents/factoria-revisor-api.md'])
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        save_agent_profile(self.root, replace(updated, description='Nueva descripción'), mode='update')
        self.assertFalse(ProjectIntegration(self.root).check()['ready'])

    def test_duplicate_missing_and_invalid_references_preserve_catalog(self) -> None:
        target = save_agent_profile(self.root, self.agent, mode='create')
        before = target.read_bytes()
        for agent, mode in ((self.agent, 'create'), (replace(self.agent, role='missing'), 'update'),
                            (replace(self.agent, skills=('missing.md',)), 'update'),
                            (replace(self.agent, role='../escape'), 'create'),
                            (replace(self.agent, role='reviewer', base_role='implementer'), 'update'),
                            (replace(self.agent, base_role='unknown'), 'update')):
            with self.subTest(agent=agent, mode=mode), self.assertRaises(ValueError):
                save_agent_profile(self.root, agent, mode=mode)
            self.assertEqual(target.read_bytes(), before)

    def test_conflict_from_other_editor_preserves_other_edit(self) -> None:
        target = save_agent_profile(self.root, self.agent, mode='create')
        stale = agent_catalog_revision(self.root)
        edited = replace(self.agent, instructions='Cambios desde otro editor')
        save_agent_profile(self.root, edited, mode='update', expected_revision=stale)
        before = target.read_bytes()
        with self.assertRaises(AgentCatalogConflict):
            save_agent_profile(self.root, replace(self.agent, name='Borrador atrasado'), expected_revision=stale, mode='update')
        self.assertEqual(target.read_bytes(), before)

    def test_concurrent_editors_cannot_overwrite_one_another(self) -> None:
        revision = agent_catalog_revision(self.root)
        barrier = threading.Barrier(2)
        def create(identifier: str):
            barrier.wait(timeout=3)
            try:
                save_agent_profile(self.root, replace(self.agent, role=identifier), mode='create', expected_revision=revision)
                return 'saved'
            except AgentCatalogConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(executor.map(create, ('first-reviewer', 'second-reviewer')), ('saved', 'conflict'))
        self.assertEqual(len(load_agent_profiles(self.root)), 6)

    def test_custom_implementer_has_only_confirmed_edit_permission(self) -> None:
        save_agent_profile(self.root, replace(self.agent, base_role='implementer'))
        exported = ProjectIntegration(self.root).plan().files['.opencode/agents/factoria-revisor-api.md']
        self.assertIn('"edit": "ask"', exported)
        self.assertIn('"*": "deny"', exported)
        self.assertNotIn('"edit": "allow"', exported)

    def test_replace_failure_preserves_bytes_and_cleans_temporary_file(self) -> None:
        target = save_agent_profile(self.root, self.agent)
        before = target.read_bytes()
        files = set(target.parent.iterdir())
        with patch('factoria.application.agent_profiles.os.replace', side_effect=OSError('Disk unavailable')):
            with self.assertRaises(OSError):
                save_agent_profile(self.root, replace(self.agent, name='Cambio'))
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(set(target.parent.iterdir()), files)

    def test_secrets_and_write_policy_prevent_catalog_writes(self) -> None:
        with self.assertRaisesRegex(ValueError, 'secreto'):
            save_agent_profile(self.root, replace(self.agent, instructions='password = "synthetic-example-secret"'))
        folder = Path.home() / '.factoria'
        folder.mkdir(parents=True)
        (folder / 'organization.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        with self.assertRaises(PermissionError):
            save_agent_profile(self.root, self.agent)
        self.assertFalse((self.root / '.factoria/agents.json').exists())

    @unittest.skipIf(os.name == 'nt', 'Symlink creation requires elevated Windows privileges')
    def test_symlinked_catalog_and_skill_are_rejected(self) -> None:
        folder = self.root / '.factoria'
        folder.mkdir()
        outside = self.root / 'outside.json'
        outside.write_text('{}')
        (folder / 'agents.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'simbólicos'):
            save_agent_profile(self.root, self.agent)
        (folder / 'agents.json').unlink()
        (self.root / 'rules.md').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'simbólicos'):
            save_agent_profile(self.root, replace(self.agent, skills=('rules.md',)))
        self.assertEqual(outside.read_text(), '{}')

    def test_legacy_roles_migrate_and_keep_custom_agents_on_builtin_edit(self) -> None:
        folder = self.root / '.factoria'
        folder.mkdir()
        (folder / 'ui-agents.json').write_text(json.dumps({'reviewer': {'profile': 'rapido', 'instructions': 'Regla anterior'}}))
        revision = agent_catalog_revision(self.root)
        save_agent_profile(self.root, self.agent, expected_revision=revision, mode='create')
        reviewer = next(a for a in load_agent_profiles(self.root) if a.role == 'reviewer')
        self.assertEqual(reviewer.instructions, 'Regla anterior')
        save_agent_profile(self.root, replace(reviewer, instructions='Regla actualizada'), mode='update')
        self.assertIn(self.agent, load_agent_profiles(self.root))
        self.assertEqual(len(load_agent_profiles(self.root)), 6)

    def test_http_create_update_conflict_and_project_pinning(self) -> None:
        (self.root / '.git').mkdir()
        UiWorkspaceSettings(self.root.parent, self.root).save()
        server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaN8NHandler)
        server.factoria_token = 'test-token'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def request(endpoint: str, data: dict, authorized: bool = True):
                headers = {'Content-Type': 'application/json'}
                if authorized:
                    headers['X-Factoria-Token'] = 'test-token'
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_address[1]}{endpoint}',
                                             data=json.dumps(data).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            payload = {**self.agent.to_mapping(), 'revision': agent_catalog_revision(self.root), 'project_path': str(self.root)}
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request('/api/agent-role/create', payload, False)
            self.assertEqual(caught.exception.code, 403)
            with patch('factoria.web_app._state', return_value={'selected_project': {'path': str(self.root)}}):
                result = request('/api/agent-role/create', payload)
                self.assertEqual(len(result['state']['agent_roles']), 6)
                payload['revision'] = result['state']['agent_catalog_revision']
                payload['instructions'] = 'Nueva instrucción'
                result = request('/api/agent-role/save', payload)
                self.assertNotEqual(payload['revision'], result['state']['agent_catalog_revision'])
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/agent-role/save', payload)
                self.assertEqual(caught.exception.code, 409)
                payload['revision'] = result['state']['agent_catalog_revision']
                payload['project_path'] = str(self.root / 'wrong-project')
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/agent-role/save', payload)
                self.assertEqual(caught.exception.code, 409)
                self.assertEqual(load_agent_profiles(self.root)[-1].instructions, 'Nueva instrucción')
                payload['project_path'] = str(self.root)
                del payload['revision']
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/agent-role/save', payload)
                self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
