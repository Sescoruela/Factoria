from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

from factoria.application.project_templates import (
    export_template, validate_template, preview_template, apply_template, read_template, TemplateConflict,
)
from factoria.application.skill_catalog import SkillDefinition, save_skill, skill_catalog_revision
from factoria.application.agent_profiles import load_agent_profiles, AgentRoleProfile, save_agent_profile
from factoria.application.workflow_presets import load_catalog
from factoria.application.project_integration import ProjectIntegration
from factoria.application.native_workflow import NativeWorkflow
from factoria.memory.loader import load_project_memory
from factoria.memory.filesystem import write_initial_memory
from factoria.project_cli import run_project_cli
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler
from factoria.web_app_n8n import FactoriaN8NHandler
from tools.acceptance_lab import prepare_project


class ProjectTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source, self.target = self.base / 'source', self.base / 'target'
        home = patch('pathlib.Path.home', return_value=self.base / 'home')
        home.start(); self.addCleanup(home.stop)
        prepare_project(self.source, 'chatgpt-checkout', 'feature', sys.executable)
        self.target.mkdir()
        subprocess.run(['git', '-C', str(self.target), 'init', '-b', 'main'], check=True, capture_output=True)
        self.data = export_template(self.source, 'Equipo API')

    def apply(self, root=None, data=None):
        root = root or self.target; data = data or self.data
        plan = preview_template(root, data)
        return apply_template(root, data, expected_token=plan['token'], confirmed=True)

    def sources(self, root=None):
        root = root or self.target
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
                if p.is_file() and '.git' not in p.relative_to(root).parts}

    def test_roundtrip_equivalent_resources_and_both_integrations(self):
        memory = replace(load_project_memory(self.source), purpose='Destination only')
        write_initial_memory(self.target, memory)
        (self.target / '.factoria').mkdir(exist_ok=True)
        (self.target / '.factoria/config.toml').write_text('[flows]\nblocked=["fix"]\n')
        before = self.sources()
        plan = preview_template(self.target, self.data)
        self.assertFalse(plan['conflicts']); self.assertEqual(self.sources(), before)
        result = self.apply()
        self.assertEqual(load_agent_profiles(self.source), load_agent_profiles(self.target))
        self.assertEqual(load_catalog(self.source), load_catalog(self.target))
        self.assertEqual(export_template(self.target, 'Equipo API'), self.data)
        for name, content in before.items():
            self.assertEqual((self.target / name).read_bytes(), content)
        self.assertTrue((Path(result['backup']) / 'journal.json').exists())
        ProjectIntegration(self.target).apply(confirmed=True)
        self.assertTrue((self.target / '.agents/skills/factoria-feature-lab/SKILL.md').exists())
        self.assertTrue((self.target / '.opencode/commands/factoria-feature-lab.md').exists())
        self.assertFalse((self.target / '.agents/skills/factoria-fix-lab/SKILL.md').exists())
        self.assertTrue(ProjectIntegration(self.target).check()['ready'])

    def test_identical_import_is_idempotent_and_other_resources_preserved(self):
        self.apply()
        extra = SkillDefinition('own', 'Own', content='Only destination')
        save_skill(self.target, extra, expected_revision=skill_catalog_revision(self.target), create=True)
        before = self.sources()
        result = self.apply()
        self.assertEqual(result['create'], []); self.assertIsNone(result['backup'])
        self.assertEqual(self.sources(), before)

    def test_foreign_skill_and_custom_agent_conflict_block_every_write(self):
        (self.target / '.factoria/skills').mkdir(parents=True)
        foreign = self.target / '.factoria/skills/LAB-RULES.md'; foreign.write_text('Foreign')
        plan = preview_template(self.target, self.data)
        self.assertIn('.factoria/skills/lab-rules.md', plan['conflicts'])
        before = self.sources()
        with self.assertRaises(TemplateConflict):self.apply()
        self.assertEqual(self.sources(), before)
        foreign.unlink(); self.apply()
        path = self.target / '.factoria/agents.json'
        data = json.loads(path.read_text()); data['lab-implementer']['instructions'] = 'Destination'
        path.write_text(json.dumps(data)); before = self.sources()
        self.assertIn('agent:lab-implementer', preview_template(self.target, self.data)['conflicts'])
        with self.assertRaises(TemplateConflict):self.apply()
        self.assertEqual(self.sources(), before)

    def test_preview_token_binds_destination_payload_and_catalogs(self):
        plan = preview_template(self.target, self.data)
        altered = deepcopy(self.data); altered['name'] = 'Changed'
        with self.assertRaises(TemplateConflict):
            apply_template(self.target, altered, expected_token=plan['token'], confirmed=True)
        save_skill(self.target, SkillDefinition('own', 'Own', content='Own'), expected_revision=skill_catalog_revision(self.target), create=True)
        with self.assertRaises(TemplateConflict):
            apply_template(self.target, self.data, expected_token=plan['token'], confirmed=True)
        with self.assertRaises(TemplateConflict):
            apply_template(self.source, self.data, expected_token=plan['token'], confirmed=True)

    def test_policy_and_confirmation_are_required(self):
        plan = preview_template(self.target, self.data)
        with self.assertRaises(PermissionError):
            apply_template(self.target, self.data, expected_token=plan['token'], confirmed=False)
        (self.target / '.factoria').mkdir()
        (self.target / '.factoria/config.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        with self.assertRaises(PermissionError):self.apply()
        self.assertFalse((self.target / '.factoria/agents.json').exists())

    def test_parallel_imports_reject_the_stale_preview(self):
        plan = preview_template(self.target, self.data)
        def importing():
            try:
                apply_template(self.target, self.data, expected_token=plan['token'], confirmed=True)
                return 'applied'
            except TemplateConflict:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: importing(), range(2))), ['applied','stale'])
        self.assertEqual(export_template(self.target, 'Equipo API'), self.data)

    def test_nonportable_fields_secrets_invalid_roles_paths_and_references(self):
        changes = [lambda d:d.update(machine_paths={}),
                   lambda d:d.update(schema_version=2),
                   lambda d:d['skills'].append(d['skills'][0]),
                   lambda d:d['skills'][0].update(id='../escape'),
                   lambda d:d['agents'][-1].update(skills=['/outside.md']),
                   lambda d:d['agents'][-1].update(skills=['docs/missing.md']),
                   lambda d:d['skills'][0].update(content='token = "'+'s'*40+'"'),
                   lambda d:d['workflows']['feature-lab']['steps'][2].update(agent_id='missing')]
        for change in changes:
            data = deepcopy(self.data);change(data)
            with self.subTest(change=change), self.assertRaises(ValueError):validate_template(data)
        self.assertFalse((self.target / '.factoria').exists())

    def test_export_does_not_include_memory_policies_machine_preferences_or_foreign_files(self):
        (self.source / '.factoria/config.toml').write_text('profile="safe"\n')
        (self.source / '.factoria/skills/foreign.md').write_text('Private foreign content')
        data = export_template(self.source, 'Portable')
        text = json.dumps(data)
        self.assertNotIn('Private foreign content', text)
        self.assertNotIn('confirmed_check_commands', text)
        self.assertNotIn('project_name', text)
        self.assertNotIn(str(self.source), text)
        self.assertEqual(set(data), {'schema_version', 'name', 'skills', 'agents', 'workflows'})

    def test_write_failure_rolls_back_and_keeps_recovery_record(self):
        import factoria.application.project_templates as module
        original = module.os.link
        calls = 0
        def fail_later(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:raise OSError('disk full')
            return original(source, target)
        with patch.object(module.os, 'link', side_effect=fail_later), self.assertRaises(OSError):self.apply()
        self.assertEqual(self.sources(), {})
        journals = list((self.target / '.git/factoria/template-imports').glob('*/journal.json'))
        self.assertEqual(json.loads(journals[0].read_text())['state'], 'failed')

    def test_failure_restores_existing_catalog_bytes(self):
        save_agent_profile(self.target, AgentRoleProfile('destination', 'equilibrado', base_role='implementer', name='Own'), mode='create')
        before = self.sources()
        import factoria.application.project_templates as module
        original = module.os.link
        def fail_workflows(source, target):
            if Path(target).name == 'workflows.json':raise OSError('disk full')
            return original(source, target)
        with patch.object(module.os, 'link', side_effect=fail_workflows), self.assertRaises(OSError):self.apply()
        self.assertEqual(self.sources(), before)

    def test_failure_preserves_later_external_edit_with_recovery_notice(self):
        import factoria.application.project_templates as module
        original = module.os.link
        def external_edit(source, target):
            if Path(target).name == 'agents.json':
                (self.target / '.factoria/skills/lab-rules.md').write_text('External edit')
                raise OSError('interrupted')
            return original(source, target)
        with patch.object(module.os, 'link', side_effect=external_edit), self.assertRaisesRegex(RuntimeError, 'copia local'):
            self.apply()
        self.assertEqual((self.target / '.factoria/skills/lab-rules.md').read_text(), 'External edit')

    def test_export_blocks_external_skill_reference_and_detectable_secret(self):
        path = self.source / '.factoria/agents.json'
        data = json.loads(path.read_text())
        data['lab-implementer']['skills'] = ['docs/rules.md']
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'catálogo exportado'):export_template(self.source, 'Portable')
        data['lab-implementer']['skills'] = []
        data['lab-implementer']['instructions'] = 'password = "'+'x'*40+'"'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'secreto'):export_template(self.source, 'Portable')

    def test_symlink_and_json_duplicate_inputs_are_rejected(self):
        (self.target / '.factoria').mkdir()
        outside = self.base / 'outside';outside.mkdir()
        try:(self.target / '.factoria/skills').symlink_to(outside, target_is_directory=True)
        except OSError:self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):self.apply()
        self.assertEqual(list(outside.iterdir()), [])
        raw = self.base / 'bad.json';raw.write_text('{"schema_version":1,"schema_version":2}')
        with self.assertRaises(ValueError):read_template(raw)

    def test_running_snapshot_is_not_changed(self):
        native = NativeWorkflow(self.source)
        flow = native.start('feature-lab', 'Observe snapshots', 'codex')
        path = self.source / '.factoria/work' / flow['flow_id'] / 'native.json'
        before = path.read_bytes()
        data = deepcopy(self.data);data['skills'].append({'id':'extra','name':'Extra','content':'Extra rules'})
        self.apply(self.source, data)
        self.assertEqual(path.read_bytes(), before)

    def test_cli_export_preview_confirm_and_read_only(self):
        path = self.base / 'portable.json'
        def cli(root, *args):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = run_project_cli(['--project', str(root), *args])
            return code, output.getvalue()
        self.assertEqual(cli(self.source, 'project', 'templates', 'export', '--name','API','--output',str(path))[0],0)
        code, text = cli(self.target, 'project','templates','import',str(path));self.assertEqual(code,0)
        token = json.loads(text)['token']
        self.assertEqual(cli(self.target,'--read-only','project','templates','import',str(path),'--yes','--token',token)[0],1)
        self.assertEqual(cli(self.target,'project','templates','import',str(path),'--yes','--token',token)[0],0)
        self.assertEqual(cli(self.source,'project','templates','export','--name','API','--output',str(path))[0],1)
        blocked = self.base / 'blocked.json'
        self.assertEqual(cli(self.source,'--read-only','project','templates','export','--name','API','--output',str(blocked))[0],1)
        (self.source / '.factoria/config.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        self.assertEqual(cli(self.source,'project','templates','export','--name','API','--output',str(blocked))[0],1)
        self.assertFalse(blocked.exists())

    def test_both_http_shells_auth_project_identity_and_apply(self):
        UiWorkspaceSettings(self.base, self.target).save()
        for handler in (FactoriaWebHandler, FactoriaN8NHandler):
            server = FactoriaHTTPServer(('127.0.0.1',0),handler);server.factoria_token='test-token'
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_address[1]}'
            def request(action,payload,auth=True):
                req=urllib.request.Request(base+'/api/template/'+action,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**({'X-Factoria-Token':'test-token'} if auth else {})})
                with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
            try:
                payload={'project_path':str(self.target),'template':self.data}
                with self.assertRaises(urllib.error.HTTPError) as error:request('preview',payload,False)
                self.assertEqual(error.exception.code,403)
                plan=request('preview',payload)
                with self.assertRaises(urllib.error.HTTPError) as error:request('apply',{**payload,'project_path':str(self.source),'token':plan['token'],'confirmed':True})
                self.assertEqual(error.exception.code,409)
                self.assertTrue(request('apply',{**payload,'token':plan['token'],'confirmed':True})['applied'])
                self.assertEqual(request('export',{'project_path':str(self.target),'name':'Export'})['template']['schema_version'],1)
                with urllib.request.urlopen(base+'/assets/templates.js') as response:self.assertIn(b'templateApply',response.read())
                with urllib.request.urlopen(base+'/') as response:self.assertIn(b'/assets/templates.js',response.read())
            finally:server.shutdown();server.server_close();thread.join()
