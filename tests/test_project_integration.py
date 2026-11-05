from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from factoria.application.agent_profiles import AgentRoleProfile, load_agent_profiles, save_agent_profile
from factoria.application.artifacts import FlowArtifactStore
from factoria.application.flow_service import FlowService
from factoria.application.history import LocalExecutionHistoryStore
from factoria.application.memory_flows import MemoryUpdateFlow, MemoryUpdateProposal
from factoria.application.native_workflow import NativeWorkflow
from factoria.application.project_integration import ProjectIntegration, START, END
from factoria.application.state_store import LocalFlowStateStore
from factoria.application.workflow_presets import default_preset, load_preset, save_preset
from factoria.domain.models import ConfirmedCommand, MemoryMetadata, ProjectKind, ProjectMemory
from factoria.memory.filesystem import write_initial_memory
from factoria.memory.loader import load_project_memory
from factoria.project_cli import run_project_cli


APPROVED = json.dumps({'result': 'approved', 'acceptance_criteria_met': True,
                      'mandatory_rules_violated': [], 'findings': [], 'risks': [],
                      'recommendation': 'Ready for approval'})


class ProjectFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='factoria native ')
        self.root = Path(self.temp.name) / 'project with spaces'
        self.root.mkdir()
        self.home = Path(self.temp.name) / 'isolated-home'
        self.home.mkdir()
        self.home_patch = patch('pathlib.Path.home', return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.addCleanup(self.temp.cleanup)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / '.gitignore').write_text('__pycache__/\n.factoria/security/\n', encoding='utf-8')
        (self.root / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
        self.commit()
        self.memory = ProjectMemory(project_name='Fixture', metadata=MemoryMetadata(
            self.git('rev-parse', 'HEAD'), date.today(), '0.2.0', ProjectKind.ACTIVE),
            confirmed_check_commands=(ConfirmedCommand('test', (sys.executable, '-c', "from pathlib import Path; ns={}; exec(compile(Path('app.py').read_text(), 'app.py', 'exec'), ns); assert ns['VALUE'] == 2")),),
            manual_verification=('Abrir la pantalla y comprobar el valor.',))
        write_initial_memory(self.root, self.memory)
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        self.git('switch', '-c', 'work/native')
        self.native = NativeWorkflow(self.root)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True,
                              text=True, encoding='utf-8').stdout.strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '--allow-empty', '-m', 'Fixture')

    def evidence(self, status, text='Evidence of the requested work and reproduction'):
        Path(status['evidence_file']).write_text(text, encoding='utf-8')


class IntegrationTests(ProjectFixture):
    def test_http_preparation_requires_token_and_explicit_confirmation(self):
        import threading
        import urllib.error
        import urllib.request
        from factoria.web_app import FactoriaHTTPServer
        from factoria.web_app_n8n import FactoriaN8NHandler
        save_agent_profile(self.root, AgentRoleProfile('reviewer', 'rapido'))
        server = FactoriaHTTPServer(('127.0.0.1', 0), FactoriaN8NHandler)
        server.factoria_token = 'fixture-token'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_address[1]}/api/project/prepare'
            def request(data, authorized=True):
                headers = {'Content-Type': 'application/json'}
                if authorized:
                    headers['X-Factoria-Token'] = 'fixture-token'
                req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=3) as response:
                    return json.load(response)
            with self.assertRaises(urllib.error.HTTPError) as error:
                request({'confirmed': True}, False)
            self.assertEqual(error.exception.code, 403)
            with patch('factoria.web_app_n8n._selected_project', return_value=self.root), patch('factoria.web_app_n8n._extended_state', return_value={}):
                self.assertFalse(request({'confirmed': False})['applied'])
                self.assertFalse(ProjectIntegration(self.root).check()['ready'])
                self.assertTrue(request({'confirmed': True})['applied'])
                self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_cli_finds_project_from_subdirectory(self):
        nested = self.root / 'src'
        nested.mkdir()
        self.assertEqual(run_project_cli(['--project', str(nested), 'project', 'check']), 0)

    def test_export_rejects_symlinks_and_ambiguous_agents_markers(self):
        import os
        (self.root / 'AGENTS.md').write_text(END + START)
        with self.assertRaisesRegex(ValueError, 'invertido'):
            ProjectIntegration(self.root).plan()
        if os.name != 'nt':
            (self.root / 'AGENTS.md').unlink()
            outside = Path(self.temp.name) / 'outside.md'
            outside.write_text('Preserve me')
            (self.root / 'AGENTS.md').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'simbólicos'):
                ProjectIntegration(self.root).apply(confirmed=True)
            self.assertEqual(outside.read_text(), 'Preserve me')

    def test_both_tools_discover_same_workflow_and_export_is_idempotent(self):
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        self.assertEqual(ProjectIntegration(self.root).plan().changed, ())
        for kind in ('fix', 'feature'):
            skill = (self.root / f'.agents/skills/factoria-{kind}/SKILL.md').read_text()
            command = (self.root / f'.opencode/commands/factoria-{kind}.md').read_text()
            guide = (self.root / f'.factoria/generated/{kind}.md').read_text()
            self.assertIn(guide, skill)
            self.assertIn(guide, command)
        self.assertIn(START, (self.root / 'AGENTS.md').read_text())
        self.assertIn('sin herramientas solo propuestas', ProjectIntegration(self.root).check()['chatgpt'])

    def test_agents_and_flows_are_tracked_not_ignored(self):
        tracked = self.git('ls-files')
        self.assertIn('.factoria/agents.json', tracked)
        self.assertIn('.factoria/workflows.json', tracked)

    def test_preserves_handwritten_agents_bytes_outside_managed_block(self):
        original = 'Normas propias\r\nTexto con acentos: revisión.\r\n'
        (self.root / 'AGENTS.md').write_bytes(original.encode())
        ProjectIntegration(self.root).apply(confirmed=True)
        written = (self.root / 'AGENTS.md').read_bytes()
        self.assertTrue(written.startswith(original.encode()))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertEqual(written, (self.root / 'AGENTS.md').read_bytes())

    def test_conflict_prevents_all_writes(self):
        target = self.root / '.agents/skills/factoria-fix/SKILL.md'
        target.write_text('User owned changes', encoding='utf-8')
        before = (self.root / 'AGENTS.md').read_bytes()
        self.assertIn('.agents/skills/factoria-fix/SKILL.md', ProjectIntegration(self.root).plan().conflicts)
        with self.assertRaisesRegex(ValueError, 'modificados'):
            ProjectIntegration(self.root).apply(confirmed=True)
        self.assertEqual(before, (self.root / 'AGENTS.md').read_bytes())
        self.assertEqual(target.read_text(), 'User owned changes')

    def test_custom_agent_instructions_skills_and_model_are_shared(self):
        (self.root / 'rules.md').write_text('Respect legacy framework.', encoding='utf-8')
        save_agent_profile(self.root, AgentRoleProfile('reviewer', 'rapido', 'codex', 'Check API compatibility.', ('rules.md',)))
        self.assertFalse(ProjectIntegration(self.root).check()['ready'])
        ProjectIntegration(self.root).apply(confirmed=True)
        text = (self.root / '.factoria/generated/feature.md').read_text()
        self.assertIn('Check API compatibility.', text)
        self.assertIn('rules.md', text)
        self.assertIn('perfil `rapido`', text)
        self.assertIn('Respect legacy framework.', (self.root / '.factoria/generated/chatgpt-context.md').read_text())

    def test_malformed_configuration_never_silently_uses_default(self):
        (self.root / '.factoria/workflows.json').write_text('{bad', encoding='utf-8')
        with self.assertRaises(ValueError):
            ProjectIntegration(self.root).plan()

    def test_invalid_skill_paths_are_rejected(self):
        for name in ('../private.md', '/tmp/private.md', 'C:/private.md', 'rules.txt'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                save_agent_profile(self.root, AgentRoleProfile('reviewer', 'potente', skills=(name,)))

    def test_secrets_in_export_are_blocked(self):
        (self.root / 'rules.md').write_text('password = "' + 'example-sensitive-value' + '"', encoding='utf-8')
        save_agent_profile(self.root, AgentRoleProfile('reviewer', 'potente', skills=('rules.md',)))
        with self.assertRaisesRegex(ValueError, 'secreto'):
            ProjectIntegration(self.root).plan()

    def test_disabled_flow_removes_only_owned_discovery_assets(self):
        (self.root / '.factoria/config.toml').write_text('[flows]\nblocked=["fix"]\n', encoding='utf-8')
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertFalse((self.root / '.agents/skills/factoria-fix/SKILL.md').exists())
        self.assertTrue((self.root / '.agents/skills/factoria-feature/SKILL.md').exists())
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        with self.assertRaises(PermissionError):
            self.native.start('fix', 'Fix', 'codex')

    def test_memory_update_keeps_routing_block(self):
        current = load_project_memory(self.root)
        proposal = MemoryUpdateProposal(current, current, (), confirmed=True)
        MemoryUpdateFlow(None, '0.2.0').apply(self.root, proposal)
        self.assertIn(START, (self.root / 'AGENTS.md').read_text())
        self.assertIn(END, (self.root / 'AGENTS.md').read_text())

    def test_legacy_settings_migrate_without_loss(self):
        for new, old in (('agents.json', 'ui-agents.json'), ('workflows.json', 'ui-workflows.json')):
            (self.root / '.factoria' / new).rename(self.root / '.factoria' / old)
        custom = default_preset('fix')
        save_preset(self.root, replace(custom, steps=tuple(replace(s, enabled=True) if s.name == 'plan' else s for s in custom.steps)))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertTrue(next(s for s in load_preset(self.root, 'fix').steps if s.name == 'plan').enabled)
        self.assertEqual(len(load_agent_profiles(self.root)), 5)

    def test_read_only_cli_cannot_prepare(self):
        self.assertEqual(run_project_cli(['--project', str(self.root), '--read-only', 'project', 'prepare', '--yes']), 1)


class NativeWorkflowTests(ProjectFixture):
    def test_named_fix_and_feature_complete_in_both_tools_with_required_approvals(self):
        for kind in ('fix', 'feature'):
            preset = default_preset(kind)
            if kind == 'fix':
                preset = replace(preset, steps=tuple(replace(step, enabled=True) if step.name == 'plan' else step for step in preset.steps))
            save_preset(self.root, replace(preset, id=kind + '-api', name='API ' + kind), create=True)
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        for tool in ('codex', 'opencode'):
            for identifier in ('fix-api', 'feature-api'):
                with self.subTest(tool=tool, identifier=identifier):
                    state = self.native.start(identifier, 'Update the API value', tool)
                    flow_id = state['flow_id']
                    self.assertEqual(state['workflow_id'], identifier)
                    approvals = []
                    while state['stage'] != 'ready_for_commit':
                        stage = state['stage']
                        self.assertEqual(state['workflow_id'], identifier)
                        if state['evidence_file']:
                            self.evidence(state, APPROVED if stage == 'review' else 'Reproduction, criteria and evidence')
                        if stage == 'implement':
                            (self.root / 'app.py').write_text('VALUE = 2\n')
                        if stage in ('approve_plan', 'approve_final'):
                            approvals.append(stage)
                            with self.assertRaises(PermissionError):
                                self.native.next(flow_id)
                        state = self.native.next(flow_id, approve_plan=stage == 'approve_plan', approve_final=stage == 'approve_final')
                    self.assertEqual(approvals, ['approve_plan', 'approve_final'])
                    self.commit()
                    self.assertEqual(self.native.lifecycle(flow_id, 'finish')['state'], 'completed')
                    (self.root / 'app.py').write_text('VALUE = 1\n')
                    self.commit()

    def test_named_cli_selection_and_snapshot_preserve_original_metadata(self):
        import contextlib
        import io
        preset = replace(default_preset('feature'), id='feature-api', name='Original API feature')
        save_preset(self.root, preset, create=True)
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = run_project_cli(['--project', str(self.root), '--read-only', 'project', 'workflows'])
        self.assertEqual(code, 0)
        self.assertIn('feature-api', [item['id'] for item in json.loads(output.getvalue())['workflows']])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = run_project_cli(['--project', str(self.root), 'native', 'start', 'feature-api', '--tool', 'codex', '--task', 'API feature'])
        self.assertEqual(code, 0)
        state = json.loads(output.getvalue())
        save_preset(self.root, replace(preset, name='Later feature name', steps=tuple(replace(step, profile='rapido') if step.name == 'explore' else step for step in preset.steps)))
        reloaded = NativeWorkflow(self.root).status(state['flow_id'])
        self.assertEqual(reloaded['workflow_id'], 'feature-api')
        self.assertEqual(reloaded['workflow_name'], 'Original API feature')
        self.assertEqual(reloaded['step'], state['step'])

    def test_named_allowlist_cannot_bypass_blocked_base_type(self):
        preset = replace(default_preset('fix'), id='fix-api', name='API correction')
        save_preset(self.root, preset, create=True)
        config = self.root / '.factoria/config.toml'
        config.write_text('[flows]\nallowed=["fix-api"]\n', encoding='utf-8')
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        with self.assertRaises(PermissionError):
            self.native.start('fix', 'Basic correction', 'codex')
        state = self.native.start('fix-api', 'API correction', 'opencode')
        config.write_text('[flows]\nblocked=["fix"]\nallowed=["fix-api"]\n', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.native.next(state['flow_id'])
        self.assertEqual(self.native.status(state['flow_id'])['stage'], 'explore')

    def test_legacy_native_snapshot_without_workflow_identifier_still_resumes(self):
        state = self.native.start('fix', 'Legacy correction', 'codex')
        path = self.native.artifacts.workspace(state['flow_id']).root / 'native.json'
        session = json.loads(path.read_text(encoding='utf-8'))
        session.pop('workflow_id')
        session.pop('workflow_name')
        path.write_text(json.dumps(session), encoding='utf-8')
        reloaded = NativeWorkflow(self.root).status(state['flow_id'])
        self.assertEqual(reloaded['workflow_id'], 'fix')
        self.assertEqual(reloaded['agent'], state['agent'])

    def test_custom_agent_platform_requires_explicit_native_handoff(self):
        agent = AgentRoleProfile('external-explorer', 'rapido', 'opencode', base_role='explorer', name='External explorer')
        save_agent_profile(self.root, agent)
        preset = load_preset(self.root, 'fix')
        save_preset(self.root, replace(preset, steps=tuple(replace(step, agent_id=agent.role) if step.name == 'explore' else step for step in preset.steps)))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        state = self.native.start('fix', 'Fix using external explorer', 'codex')
        self.evidence(state)
        with self.assertRaisesRegex(ValueError, 'opencode'):
            self.native.next(state['flow_id'])
        state = self.native.next(state['flow_id'], tool='opencode')
        self.assertEqual(state['tool'], 'opencode')
        self.assertEqual(state['stage'], 'implement')

    def test_custom_agents_complete_fix_and_feature_in_both_native_tools(self):
        from factoria.orchestration.models import AgentRole
        for role in AgentRole:
            save_agent_profile(self.root, AgentRoleProfile('specialist-' + role.value, 'rapido',
                               instructions='Specialist rules for ' + role.value, base_role=role.value,
                               name='Specialist ' + role.value))
        for kind in ('fix', 'feature'):
            preset = load_preset(self.root, kind)
            save_preset(self.root, replace(preset, steps=tuple(replace(step, agent_id='specialist-' + step.role) for step in preset.steps)))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        for tool in ('codex', 'opencode'):
            for kind in ('fix', 'feature'):
                with self.subTest(tool=tool, kind=kind):
                    state = self.native.start(kind, 'Change value with specialists', tool)
                    flow_id = state['flow_id']
                    while state['stage'] != 'ready_for_commit':
                        stage = state['stage']
                        if state['agent'] is not None:
                            self.assertEqual(state['agent']['role'], 'specialist-' + state['step']['role'])
                            self.assertEqual(state['step']['agent_id'], state['agent']['role'])
                            self.assertIn('Specialist rules', state['agent']['instructions'])
                        if state['evidence_file']:
                            self.evidence(state, APPROVED if stage == 'review' else 'Reproduction, criteria and evidence')
                        if stage == 'implement':
                            (self.root / 'app.py').write_text('VALUE = 2\n')
                        if stage in ('approve_plan', 'approve_final'):
                            with self.assertRaises(PermissionError):
                                self.native.next(flow_id)
                        state = self.native.next(flow_id, approve_plan=stage == 'approve_plan', approve_final=stage == 'approve_final')
                    self.commit()
                    self.assertEqual(self.native.lifecycle(flow_id, 'finish')['state'], 'completed')
                    (self.root / 'app.py').write_text('VALUE = 1\n')
                    self.commit()

    def test_custom_assignment_is_frozen_despite_later_catalog_and_workflow_edits(self):
        (self.root / 'custom-rules.md').write_text('Original custom rules', encoding='utf-8')
        agent = AgentRoleProfile('custom-explorer', 'rapido', instructions='Original agent instructions',
                                 skills=('custom-rules.md',), base_role='explorer', name='Custom explorer')
        save_agent_profile(self.root, agent)
        preset = load_preset(self.root, 'fix')
        save_preset(self.root, replace(preset, steps=tuple(replace(step, agent_id=agent.role) if step.name == 'explore' else step for step in preset.steps)))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        state = self.native.start('fix', 'Fix with custom explorer', 'codex')
        frozen_agent, frozen_step = state['agent'], state['step']
        save_agent_profile(self.root, replace(agent, instructions='Later instructions', profile='potente'))
        (self.root / 'custom-rules.md').write_text('Later skill rules', encoding='utf-8')
        save_preset(self.root, default_preset('fix'))
        restored = NativeWorkflow(self.root).status(state['flow_id'])
        self.assertEqual(restored['agent'], frozen_agent)
        self.assertEqual(restored['step'], frozen_step)
        self.assertEqual(restored['agent']['role'], agent.role)
        self.assertIn('Original custom rules', restored['agent']['skill_contents']['custom-rules.md'])

    def test_skill_edit_keeps_the_running_agent_content_snapshot(self):
        from factoria.application.skill_catalog import SkillDefinition, save_skill, skill_catalog_revision
        skill = SkillDefinition('exploration', 'Exploration', content='Original exploration instructions')
        save_skill(self.root, skill, expected_revision=skill_catalog_revision(self.root), create=True)
        save_agent_profile(self.root, AgentRoleProfile('explorer', 'equilibrado', skills=(skill.path,)))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        state = self.native.start('fix', 'Fix value', 'codex')
        frozen = state['agent']['skill_contents'][skill.path]
        save_skill(self.root, replace(skill, content='Updated exploration instructions'), expected_revision=skill_catalog_revision(self.root))
        self.assertEqual(self.native.status(state['flow_id'])['agent']['skill_contents'][skill.path], frozen)
        self.assertIn(skill.content, frozen)

    def test_workflow_edits_preserve_running_flow_snapshot(self):
        state = self.native.start('fix', 'Fix value', 'codex')
        original = state['step']
        preset = load_preset(self.root, 'fix')
        updated = replace(preset, steps=tuple(replace(step, profile='potente') if step.name == 'explore' else step for step in preset.steps))
        save_preset(self.root, updated)
        self.assertEqual(self.native.status(state['flow_id'])['step'], original)

    def test_agent_edits_preserve_the_running_flow_snapshot(self):
        state = self.native.start('fix', 'Fix value', 'codex')
        original = state['agent']
        save_agent_profile(self.root, AgentRoleProfile('explorer', 'potente', instructions='New exploration rules'))
        custom = AgentRoleProfile('api-reviewer', 'potente', base_role='reviewer', name='API reviewer')
        save_agent_profile(self.root, custom, mode='create')
        self.assertEqual(self.native.status(state['flow_id'])['agent'], original)

    def test_public_cli_uses_prepared_project_without_nested_agent(self):
        import os
        for tool in ('codex', 'opencode'):
            env = os.environ.copy()
            env['HOME'] = str(self.home)
            env['USERPROFILE'] = str(self.home)
            command = [sys.executable, '-m', 'factoria', '--project', str(self.root)]
            def run(*args):
                result = subprocess.run([*command, *args], cwd=self.root, env=env, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            self.assertTrue(run('project', 'check')['ready'])
            state = run('native', 'start', 'fix', '--tool', tool, '--task', 'Fix value')
            flow_id = state['flow_id']
            Path(state['evidence_file']).write_text('Reproduce VALUE=1; expected VALUE=2')
            state = run('native', 'next', flow_id)
            (self.root / 'app.py').write_text('VALUE = 2\n')
            Path(state['evidence_file']).write_text('Minimal change to the value')
            run('native', 'next', flow_id)
            state = run('native', 'next', flow_id)
            Path(state['evidence_file']).write_text(APPROVED)
            self.assertEqual(run('native', 'next', flow_id)['stage'], 'ready_for_commit')
            self.commit()
            self.assertEqual(run('native', 'finish', flow_id)['state'], 'completed')
            (self.root / 'app.py').write_text('VALUE = 1\n')
            self.commit()

    def test_complete_fix_and_feature_in_both_tools_without_llm_calls(self):
        for tool in ('codex', 'opencode'):
            for kind in ('fix', 'feature'):
                with self.subTest(tool=tool, kind=kind):
                    (self.root / 'app.py').write_text('VALUE = 1\n')
                    self.commit()
                    state = self.native.start(kind, 'Change value', tool)
                    flow_id = state['flow_id']
                    while state['stage'] != 'ready_for_commit':
                        stage = state['stage']
                        if state['evidence_file']:
                            self.evidence(state, APPROVED if stage == 'review' else 'Reproduction, criteria and evidence')
                        if stage == 'implement':
                            (self.root / 'app.py').write_text('VALUE = 2\n')
                        state = self.native.next(flow_id, approve_plan=stage == 'approve_plan', approve_final=stage == 'approve_final')
                    self.commit()
                    self.assertEqual(self.native.lifecycle(flow_id, 'finish')['state'], 'completed')
                    self.assertFalse(self.native.store.incomplete())
                    history = LocalExecutionHistoryStore(self.root)
                    self.assertTrue((history.history_root() / f'{flow_id}.json').exists())

    def test_stage_cannot_advance_without_evidence_or_approval(self):
        state = self.native.start('feature', 'Feature', 'codex')
        with self.assertRaisesRegex(ValueError, 'Falta evidencia'):
            self.native.next(state['flow_id'])
        self.evidence(state)
        state = self.native.next(state['flow_id'])
        self.evidence(state)
        state = self.native.next(state['flow_id'])
        self.assertEqual(state['stage'], 'approve_plan')
        with self.assertRaises(PermissionError):
            self.native.next(state['flow_id'])
        self.assertEqual(self.native.next(state['flow_id'], approve_plan=True)['stage'], 'implement')

    def to_verify(self):
        state = self.native.start('fix', 'Fix value', 'codex')
        self.evidence(state)
        state = self.native.next(state['flow_id'])
        self.evidence(state)
        return self.native.next(state['flow_id'])

    def test_failed_check_blocks_review_and_can_be_retried(self):
        state = self.to_verify()
        with self.assertRaisesRegex(ValueError, 'Verificación obligatoria fallida'):
            self.native.next(state['flow_id'])
        self.assertEqual(self.native.status(state['flow_id'])['stage'], 'verify')
        (self.root / 'app.py').write_text('VALUE = 2\n')
        self.assertEqual(self.native.next(state['flow_id'])['stage'], 'review')

    def test_changes_after_verification_invalidate_review(self):
        state = self.to_verify()
        (self.root / 'app.py').write_text('VALUE = 2\n')
        state = self.native.next(state['flow_id'])
        self.evidence(state, APPROVED)
        (self.root / 'app.py').write_text('VALUE = 3\n')
        with self.assertRaisesRegex(ValueError, 'después de verificar'):
            self.native.next(state['flow_id'])
        self.assertEqual(self.native.retry(state['flow_id'])['stage'], 'verify')
        self.assertFalse(Path(state['evidence_file']).exists())

    def test_only_one_flow_across_native_and_orchestrated_modes(self):
        state = self.native.start('fix', 'Fix', 'codex')
        service = FlowService(FlowArtifactStore(self.root), LocalFlowStateStore(FlowArtifactStore(self.root)))
        with self.assertRaises(RuntimeError):
            service.create(flow_id='other', kind='fix')
        self.native.lifecycle(state['flow_id'], 'pause')
        with self.assertRaises(ValueError):
            self.native.next(state['flow_id'])
        self.native.lifecycle(state['flow_id'], 'resume')
        self.assertEqual(self.native.lifecycle(state['flow_id'], 'cancel', confirmed=True)['state'], 'cancelled')
        self.assertTrue((self.root / 'app.py').exists())

    def test_main_dirty_tree_and_unsafe_flow_ids_block(self):
        self.git('switch', 'main')
        with self.assertRaisesRegex(ValueError, 'rama de trabajo'):
            self.native.start('fix', 'Fix', 'codex')
        self.git('switch', 'work/native')
        (self.root / 'app.py').write_text('VALUE = 3\n')
        with self.assertRaisesRegex(ValueError, 'limpio'):
            self.native.start('fix', 'Fix', 'codex')
        with self.assertRaises(ValueError):
            self.native.status('../outside')

    def test_project_and_organization_policy_block_native_writes(self):
        folder = self.home / '.factoria'
        folder.mkdir()
        (folder / 'organization.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        with self.assertRaises(PermissionError):
            self.native.start('fix', 'Fix', 'codex')

    def test_no_automated_checks_requires_human_manual_confirmation(self):
        manual = replace(self.memory, confirmed_check_commands=())
        MemoryUpdateFlow(None, '0.2.0').apply(self.root, MemoryUpdateProposal(self.memory, manual, (), confirmed=True))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        state = self.to_verify()
        with self.assertRaisesRegex(PermissionError, 'humana'):
            self.native.next(state['flow_id'])
        self.assertTrue(self.native.status(state['flow_id'])['manual_steps'])
        self.assertEqual(self.native.next(state['flow_id'], confirm_manual=True)['stage'], 'review')

    def test_secret_in_new_nested_file_blocks_before_advancing(self):
        state = self.native.start('fix', 'Fix', 'codex')
        self.evidence(state)
        folder = self.root / 'new folder'
        folder.mkdir()
        (folder / 'settings.txt').write_text('password = "synthetic-example-secret"')
        with self.assertRaisesRegex(PermissionError, 'secreto'):
            self.native.next(state['flow_id'])
        self.assertEqual(self.native.status(state['flow_id'])['stage'], 'explore')

    def test_renamed_destination_with_unicode_is_the_scanned_path(self):
        self.git('mv', 'app.py', 'cálculo nuevo.py')
        self.assertIn('cálculo nuevo.py', __import__('factoria.security', fromlist=['SecretScanner']).SecretScanner.changed_paths(self.root))
        from factoria.application.git_lifecycle import GitLifecycle
        self.assertIn('cálculo nuevo.py', tuple(c.path for c in GitLifecycle(self.root).changes()))

    def test_verification_attempt_limit_is_persisted(self):
        state = self.to_verify()
        for _ in range(3):
            with self.assertRaisesRegex(ValueError, 'Verificación obligatoria fallida'):
                self.native.next(state['flow_id'])
        (self.root / 'app.py').write_text('VALUE = 2\n')
        with self.assertRaisesRegex(ValueError, 'tres verificaciones'):
            self.native.next(state['flow_id'])

    def test_declared_external_contract_requires_separate_human_review(self):
        from factoria.domain.models import ContractMemory, ExternalDependency
        external = replace(self.memory, contracts=(ContractMemory('API', ('app.py',), affects_external=('consumer',)),),
                           external_dependencies=(ExternalDependency('consumer', 'example/consumer'),))
        MemoryUpdateFlow(None, '0.2.0').apply(self.root, MemoryUpdateProposal(self.memory, external, (), confirmed=True))
        ProjectIntegration(self.root).apply(confirmed=True)
        self.commit()
        state = self.native.start('feature', 'Change API', 'codex')
        for stage in ('explore', 'plan'):
            self.assertEqual(state['stage'], stage)
            self.evidence(state)
            state = self.native.next(state['flow_id'])
        state = self.native.next(state['flow_id'], approve_plan=True)
        (self.root / 'app.py').write_text('VALUE = 2\n')
        self.evidence(state)
        state = self.native.next(state['flow_id'])
        with self.assertRaisesRegex(PermissionError, 'consumidores externos'):
            self.native.next(state['flow_id'])
        self.assertEqual(self.native.status(state['flow_id'])['external_impact'], ['consumer'])
        self.assertEqual(self.native.next(state['flow_id'], confirm_external_impact=True)['stage'], 'review')

    def test_blocking_review_never_reaches_commit(self):
        state = self.to_verify()
        (self.root / 'app.py').write_text('VALUE = 2\n')
        state = self.native.next(state['flow_id'])
        review = json.loads(APPROVED)
        review['result'] = 'changes_required'
        review['acceptance_criteria_met'] = False
        self.evidence(state, json.dumps(review))
        with self.assertRaisesRegex(ValueError, 'Review bloqueante'):
            self.native.next(state['flow_id'])
        with self.assertRaises(ValueError):
            self.native.lifecycle(state['flow_id'], 'finish')


if __name__ == '__main__':
    unittest.main()
