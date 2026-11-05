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

from factoria.application.agent_profiles import AgentRoleProfile, save_agent_profile
from factoria.application.project_integration import ProjectIntegration
from factoria.application.skill_catalog import (
    SkillCatalogConflict, SkillDefinition, save_skill, skill_catalog_revision, skill_catalog_snapshot,
)
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer
from factoria.web_app_n8n import FactoriaN8NHandler


class SkillCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        home = patch('pathlib.Path.home', return_value=self.root / 'home')
        home.start()
        self.addCleanup(home.stop)
        self.skill = SkillDefinition('revision-api', 'Revisión API', 'Compatibilidad', '# Revisión\r\n\n- Mantener contratos.  \n')

    def create(self, skill=None):
        return save_skill(self.root, skill or self.skill, expected_revision=skill_catalog_revision(self.root), create=True)

    def test_create_edit_reopen_preserves_exact_unicode_content_and_other_skills(self):
        self.create()
        self.create(replace(self.skill, id='testing', name='Tests'))
        skills, revision, _foreign = skill_catalog_snapshot(self.root)
        self.assertEqual(skills[0], self.skill)
        updated = replace(self.skill, name='Revisión HTTP', description='Códigos', content='  # Código\r\n\n```json\n{}\n```\n\n')
        save_skill(self.root, updated, expected_revision=revision)
        reloaded = {s.id: s for s in skill_catalog_snapshot(self.root)[0]}
        self.assertEqual(reloaded[updated.id], updated)
        self.assertEqual(reloaded['testing'].content, self.skill.content)

    def test_duplicate_and_foreign_file_are_never_overwritten(self):
        path = self.create()
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Ya existe'):
            self.create()
        self.assertEqual(path.read_bytes(), original)
        foreign = path.parent / 'foreign.md'
        foreign.write_text('User-owned Markdown', encoding='utf-8')
        candidate = replace(self.skill, id='foreign')
        with self.assertRaises(ValueError):
            self.create(candidate)
        with self.assertRaisesRegex(ValueError, 'ajeno'):
            save_skill(self.root, candidate, expected_revision=skill_catalog_revision(self.root))
        self.assertEqual(foreign.read_text(), 'User-owned Markdown')
        self.assertEqual(skill_catalog_snapshot(self.root)[2], ('foreign.md',))

    def test_invalid_ids_references_and_types_cannot_escape_project(self):
        for identifier in ('../outside', '/outside', 'C:/outside', 'MixedCase', 'nul', 'con', 'lpt1', ''):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.create(replace(self.skill, id=identifier))
        with self.assertRaises(ValueError):
            SkillDefinition.from_mapping({'id': 'good', 'name': 'Name', 'content': ['bad']})
        with self.assertRaises(ValueError):
            self.create(replace(self.skill, content=' '))
        with self.assertRaises(ValueError):
            save_agent_profile(self.root, AgentRoleProfile('reviewer', 'potente', skills=('.factoria/skills/missing.md',)))

    def test_stale_revision_cannot_overwrite_external_edit(self):
        path = self.create()
        revision = skill_catalog_revision(self.root)
        path.write_bytes(path.read_bytes() + b'\nExternal edit')
        before = path.read_bytes()
        with self.assertRaises(SkillCatalogConflict):
            save_skill(self.root, replace(self.skill, content='Draft'), expected_revision=revision)
        self.assertEqual(path.read_bytes(), before)

    def test_concurrent_editors_get_one_save_and_one_conflict(self):
        self.create()
        revision = skill_catalog_revision(self.root)
        barrier = threading.Barrier(2)
        def edit(content):
            barrier.wait(timeout=5)
            try:
                save_skill(self.root, replace(self.skill, content=content), expected_revision=revision)
                return 'saved'
            except SkillCatalogConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(executor.map(edit, ('First', 'Second')), ('saved', 'conflict'))

    def test_atomic_replace_failure_preserves_bytes_and_cleans_temporary_file(self):
        path = self.create()
        before = path.read_bytes()
        files = set(path.parent.iterdir())
        with patch('factoria.application.skill_catalog.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                save_skill(self.root, replace(self.skill, content='New'), expected_revision=skill_catalog_revision(self.root))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(set(path.parent.iterdir()), files)

    def test_exclusive_create_does_not_replace_a_late_foreign_file(self):
        target = self.root / self.skill.path
        real_link = os.link
        def competing_create(source, destination):
            target.write_text('Preserve foreign content', encoding='utf-8')
            return real_link(source, destination)
        with patch('factoria.application.skill_catalog.os.link', side_effect=competing_create):
            with self.assertRaises(SkillCatalogConflict):
                self.create()
        self.assertEqual(target.read_text(), 'Preserve foreign content')
        self.assertEqual([p.name for p in target.parent.iterdir()], [target.name])

    def test_secret_and_write_policy_block_changes(self):
        with self.assertRaisesRegex(ValueError, 'secreto'):
            self.create(replace(self.skill, content='password = "synthetic-example-secret"'))
        folder = Path.home() / '.factoria'
        folder.mkdir(parents=True)
        (folder / 'organization.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        with self.assertRaises(PermissionError):
            self.create()
        self.assertFalse((self.root / self.skill.path).exists())

    @unittest.skipIf(os.name == 'nt', 'Windows symlink creation needs elevated privileges')
    def test_symlinked_catalog_cannot_escape(self):
        folder = self.root / '.factoria'
        folder.mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        (folder / 'skills').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'simbólicos'):
            self.create()
        self.assertEqual(list(outside.iterdir()), [])

    def test_malformed_managed_header_blocks_writes_without_data_loss(self):
        path = self.create()
        path.write_text('<!-- factoria:skill:v1 -->\nBROKEN', encoding='utf-8')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Skill no válida'):
            self.create(replace(self.skill, id='another'))
        self.assertEqual(path.read_bytes(), before)

    def test_assign_to_agent_and_prepare_both_tools_with_stale_detection(self):
        self.create()
        save_agent_profile(self.root, AgentRoleProfile('reviewer', 'potente', skills=(self.skill.path,)))
        plan = ProjectIntegration(self.root).plan()
        self.assertIn(self.skill.path, plan.files['.agents/skills/factoria-fix/SKILL.md'])
        self.assertIn(self.skill.path, plan.files['.opencode/agents/factoria-reviewer.md'])
        self.assertIn(self.skill.content, plan.files['.factoria/generated/skills.md'])
        self.assertIn('Revisión API', plan.files['.factoria/generated/chatgpt-context.md'])
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        save_skill(self.root, replace(self.skill, content='New skill instructions'), expected_revision=skill_catalog_revision(self.root))
        self.assertFalse(ProjectIntegration(self.root).check()['ready'])
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])

    def test_http_auth_conflicts_project_pin_and_asset_packaging(self):
        (self.root / '.git').mkdir()
        UiWorkspaceSettings(self.root.parent, self.root).save()
        server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaN8NHandler)
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
            with urllib.request.urlopen(base + '/assets/skills.js', timeout=3) as response:
                self.assertIn(b'saveSkill', response.read())
                self.assertIn('javascript', response.headers['Content-Type'])
            payload = {**self.skill.to_mapping(), 'revision': skill_catalog_revision(self.root), 'project_path': str(self.root)}
            with self.assertRaises(urllib.error.HTTPError) as caught:
                request('/api/skill/create', payload, False)
            self.assertEqual(caught.exception.code, 403)
            with patch('factoria.web_app_n8n._state', return_value={'selected_project': {'path': str(self.root)}}):
                result = request('/api/skill/create', payload)
                self.assertEqual(result['state']['skills'][0]['content'], self.skill.content)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/skill/save', payload)
                self.assertEqual(caught.exception.code, 409)
                payload['revision'] = result['state']['skill_catalog_revision']
                payload['project_path'] = str(self.root / 'another')
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/skill/save', payload)
                self.assertEqual(caught.exception.code, 409)
                payload['project_path'] = str(self.root)
                del payload['revision']
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request('/api/skill/save', payload)
                self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
