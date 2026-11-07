from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

from factoria.application import config_recovery as recovery
from factoria.application.config_schema import schema_version
from factoria.application.agent_profiles import AgentRoleProfile, save_agent_profile, load_agent_profiles, agent_catalog_revision
from factoria.application.skill_catalog import SkillDefinition, save_skill, skill_catalog_revision
from factoria.application.workflow_presets import default_preset, save_preset
from factoria.application.project_integration import ProjectIntegration
from factoria.project_cli import run_project_cli
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler
from factoria.web_app_n8n import FactoriaN8NHandler


class ConfigRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project';self.root.mkdir()
        subprocess.run(['git','init','-b','main',str(self.root)],check=True,capture_output=True)
        self.home=Path(self.temp.name)/'home';self.home.mkdir()
        self.home_patch=patch('pathlib.Path.home',return_value=self.home);self.home_patch.start();self.addCleanup(self.home_patch.stop)

    def apply(self,action,identifier=None):
        plan=recovery.preview_config(self.root,action,identifier)
        self.assertEqual(plan['conflicts'],[])
        return recovery.apply_config(self.root,action,identifier=identifier,token=plan['token'],confirmed=True)

    def files(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.root).parts}

    def legacy(self):
        folder=self.root/'.factoria';folder.mkdir(exist_ok=True)
        (folder/'ui-agents.json').write_text(json.dumps({'reviewer':{'profile':'potente','instructions':'Verificar contratos'}}))
        (folder/'ui-workflows.json').write_text(json.dumps({'feature':default_preset('feature').to_mapping()}))

    def test_preview_no_project_writes_migrates_legacy_and_preserves_bytes_snapshots(self):
        self.legacy()
        for name in ('.factoria/work/snapshot.json','docs/memoria/estado.md','AGENTS.md'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('KEEP '+name)
        before=self.files();plan=recovery.preview_config(self.root,'migrate')
        self.assertEqual(self.files(),before);self.assertEqual(schema_version(self.root),0)
        result=self.apply('migrate');self.assertEqual(schema_version(self.root),1)
        for name,content in before.items():self.assertEqual((self.root/name).read_bytes(),content)
        self.assertEqual((self.root/'.factoria/agents.json').read_bytes(),before['.factoria/ui-agents.json'])
        self.assertEqual(self.apply('migrate')['backup_id'],None)
        self.apply('restore',result['backup_id']);self.assertEqual(self.files(),before)
        self.assertNotIn('instructions',json.dumps(plan));self.assertEqual(recovery.pending_recoveries(self.root),[])

    def test_checkpoint_restore_reviews_removals_and_keeps_history(self):
        save_agent_profile(self.root,AgentRoleProfile('reviewer','rapido',instructions='Inicial'))
        self.apply('migrate');before=self.files();copy=self.apply('snapshot')
        save_agent_profile(self.root,AgentRoleProfile('reviewer','potente',instructions='Nuevo'))
        save_skill(self.root,SkillDefinition('new-skill','Skill','', '# Temporal'),expected_revision=skill_catalog_revision(self.root),create=True)
        plan=recovery.preview_config(self.root,'restore',copy['backup_id'])
        self.assertIn('.factoria/skills/new-skill.md',plan['removed'])
        self.apply('restore',copy['backup_id']);self.assertEqual(self.files(),before)

    def test_stale_token_confirmation_and_policy_block_without_writes(self):
        plan=recovery.preview_config(self.root,'migrate')
        with self.assertRaises(PermissionError):recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=False)
        p=self.root/'.factoria/agents.json';p.parent.mkdir(exist_ok=True);p.write_text('{}')
        before=self.files()
        with self.assertRaisesRegex(ValueError,'obsoleto'):recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=True)
        self.assertEqual(self.files(),before)
        (self.root/'.factoria/config.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        plan=recovery.preview_config(self.root,'snapshot')
        with self.assertRaises((ValueError,PermissionError)):recovery.apply_config(self.root,'snapshot',token=plan['token'],confirmed=True)

    def test_future_version_invalid_manifest_and_duplicate_keys_block_readers_writers(self):
        folder=self.root/'.factoria';folder.mkdir()
        for raw in ('{"schema_version": 99}','{"schema_version": true}','{"schema_version":1,"extra":2}','{"schema_version":1,"schema_version":1}'):
            (folder/'schema.json').write_text(raw);before=self.files()
            self.assertIsNotNone(recovery.config_status(self.root)['error'])
            for call in (lambda:load_agent_profiles(self.root),lambda:save_agent_profile(self.root,AgentRoleProfile('reviewer','rapido')),lambda:save_preset(self.root,default_preset('fix')),lambda:ProjectIntegration(self.root).apply(confirmed=True)):
                with self.assertRaises(ValueError):call()
            self.assertEqual(self.files(),before)

    def test_divergent_legacy_catalogs_never_overwrite(self):
        self.legacy();(self.root/'.factoria/agents.json').write_text('{}')
        plan=recovery.preview_config(self.root,'migrate');self.assertTrue(plan['conflicts']);before=self.files()
        with self.assertRaises(ValueError):recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=True)
        self.assertEqual(self.files(),before)

    def test_failure_after_first_write_leaves_durable_recoverable_intent_and_blocks_edits(self):
        self.legacy();before=self.files();plan=recovery.preview_config(self.root,'migrate');write=recovery._write
        def fail(path,content):
            if path==self.root/'.factoria/schema.json':raise OSError('simulated storage failure')
            return write(path,content)
        with patch.object(recovery,'_write',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'interrumpida'):recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=True)
        pending=recovery.pending_recoveries(self.root);self.assertEqual(len(pending),1)
        from factoria.application.project_templates import apply_template
        from factoria.application.resource_lifecycle import apply_resource
        for call in (lambda:apply_template(self.root,{},expected_token='',confirmed=True),lambda:apply_resource(self.root,{},token='',confirmed=True),lambda:save_agent_profile(self.root,AgentRoleProfile('reviewer','rapido')),lambda:ProjectIntegration(self.root).apply(confirmed=True),lambda:save_skill(self.root,SkillDefinition('test','Test','','hello'),expected_revision=skill_catalog_revision(self.root),create=True)):
            with self.assertRaisesRegex(ValueError,'pendiente'):call()
        self.apply('restore',pending[0]);self.assertEqual(self.files(),before);self.assertEqual(recovery.pending_recoveries(self.root),[])
        save_agent_profile(self.root,AgentRoleProfile('reviewer','rapido'))

    def test_process_interruption_and_interrupted_recovery_can_be_retried(self):
        self.legacy();before=self.files();write=recovery._write;plan=recovery.preview_config(self.root,'migrate')
        def crash(path,content):
            if path==self.root/'.factoria/schema.json':raise SystemExit('simulated process exit')
            return write(path,content)
        with patch.object(recovery,'_write',side_effect=crash):
            with self.assertRaises(SystemExit):recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=True)
        identifier=recovery.pending_recoveries(self.root)[0]
        plan=recovery.preview_config(self.root,'restore',identifier)
        with patch.object(recovery,'_write',side_effect=OSError('second failure')):
            with self.assertRaises(ValueError):recovery.apply_config(self.root,'restore',identifier=identifier,token=plan['token'],confirmed=True)
        self.apply('restore',identifier);self.assertEqual(self.files(),before)

    def test_external_edit_after_crash_is_not_overwritten(self):
        self.legacy();write=recovery._write;plan=recovery.preview_config(self.root,'migrate')
        def crash(path,content):
            if path==self.root/'.factoria/schema.json':raise OSError('stop')
            return write(path,content)
        with patch.object(recovery,'_write',side_effect=crash):
            with self.assertRaises(ValueError):recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=True)
        identifier=recovery.pending_recoveries(self.root)[0]
        p=self.root/'.factoria/agents.json';p.write_text('{"reviewer":{"profile":"potente","instructions":"External"}}')
        plan=recovery.preview_config(self.root,'restore',identifier);self.assertTrue(plan['conflicts']);before=self.files()
        with self.assertRaises(ValueError):recovery.apply_config(self.root,'restore',identifier=identifier,token=plan['token'],confirmed=True)
        self.assertEqual(self.files(),before)

    def test_secret_oversize_corrupt_backup_and_traversal_are_rejected(self):
        folder=self.root/'.factoria';folder.mkdir()
        (folder/'config.toml').write_text('api_key = "sk-'+'x'*40+'"\n')
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'snapshot')
        self.assertEqual(recovery.config_status(self.root)['backups'],[])
        (folder/'config.toml').write_bytes(b' '*(2*1024*1024+1))
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'snapshot')
        (folder/'config.toml').unlink()
        copy=self.apply('snapshot')
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'restore','../config')
        backup=recovery._folder(self.root)/(copy['backup_id']+'.json');record=json.loads(backup.read_text());record['before']['../../evil']=None;backup.write_text(json.dumps(record))
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'restore',copy['backup_id'])

    def test_symlink_and_corrupt_json_fail_without_project_writes(self):
        folder=self.root/'.factoria';folder.mkdir()
        target=Path(self.temp.name)/'outside';target.write_text('{}')
        link=folder/'agents.json'
        try:link.symlink_to(target)
        except OSError:self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'migrate')
        self.assertEqual(target.read_text(),'{}');link.unlink();link.write_text('{broken')
        before=self.files()
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'migrate')
        self.assertEqual(self.files(),before)

    def test_cli_read_only_preview_and_apply_gate(self):
        prefix=['--project',str(self.root),'--read-only','project','config']
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(run_project_cli(prefix+['migrate']),0)
            self.assertEqual(run_project_cli(prefix+['migrate','--yes']),1)
            self.assertEqual(run_project_cli(prefix+['status']),0)
        self.assertEqual(schema_version(self.root),0)

    def test_both_http_shells_auth_project_pin_and_confirmed_migration(self):
        UiWorkspaceSettings(self.root.parent,self.root).save()
        for handler in (FactoriaN8NHandler,FactoriaWebHandler):
            server=FactoriaHTTPServer(('127.0.0.1',0),handler);server.factoria_token='test-token'
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                base='http://127.0.0.1:'+str(server.server_address[1])
                def request(path,data,token='test-token'):
                    req=urllib.request.Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Factoria-Token':token})
                    return json.load(urllib.request.urlopen(req,timeout=5))
                for data,token,code in [({'project_path':str(self.root)},'',403),({'project_path':str(self.root.parent)},'test-token',409)]:
                    with self.assertRaises(urllib.error.HTTPError) as caught:request('/api/config/status',data,token)
                    self.assertEqual(caught.exception.code,code)
                payload={'project_path':str(self.root),'action':'migrate'};plan=request('/api/config/preview',payload)
                result=request('/api/config/apply',{**payload,'token':plan['token'],'confirmed':True});self.assertTrue(result['applied'])
                with urllib.request.urlopen(base+'/assets/configuration.js',timeout=5) as r:self.assertIn(b'configPreview',r.read())
            finally:server.shutdown();server.server_close();t.join(timeout=2)

    def test_real_native_snapshot_and_memory_survive_migration_and_restore(self):
        import sys
        from tools.acceptance_lab import prepare_project
        from factoria.application.native_workflow import NativeWorkflow
        self.root=Path(self.temp.name)/'native-project'
        prepare_project(self.root,'chatgpt-checkout','feature',sys.executable)
        flow=NativeWorkflow(self.root).start('feature-lab','Conservar snapshot','codex')
        work=self.root/'.factoria/work'/flow['flow_id']
        frozen={p.relative_to(work):p.read_bytes() for p in work.rglob('*') if p.is_file()}
        memory={p.relative_to(self.root):p.read_bytes() for p in (self.root/'docs/memoria').glob('*.md')}
        migration=self.apply('migrate');copy=self.apply('snapshot')
        save_agent_profile(self.root,AgentRoleProfile('reviewer','rapido',instructions='Cambiar catálogo, no snapshot'))
        self.apply('restore',copy['backup_id']);self.apply('restore',migration['backup_id'])
        self.assertEqual(frozen,{p.relative_to(work):p.read_bytes() for p in work.rglob('*') if p.is_file()})
        self.assertEqual(memory,{p.relative_to(self.root):p.read_bytes() for p in (self.root/'docs/memoria').glob('*.md')})

    def test_concurrent_migrations_only_apply_the_reviewed_revision_once(self):
        from concurrent.futures import ThreadPoolExecutor
        plan=recovery.preview_config(self.root,'migrate')
        def run():
            try:
                recovery.apply_config(self.root,'migrate',token=plan['token'],confirmed=True);return 'applied'
            except ValueError:return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertCountEqual(list(pool.map(lambda _:run(),range(2))),['applied','stale'])

    def test_corrupt_hash_or_cross_project_backup_is_refused(self):
        copy=self.apply('snapshot');target=recovery._folder(self.root)/(copy['backup_id']+'.json')
        raw=json.loads(target.read_text());raw['before_hash']='0'*64;target.write_text(json.dumps(raw))
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'restore',copy['backup_id'])
        raw['project']=str(self.root.parent);target.write_text(json.dumps(raw))
        with self.assertRaises(ValueError):recovery.preview_config(self.root,'restore',copy['backup_id'])

    def test_backup_limit_is_checked_before_creating_an_unreadable_overflow(self):
        before=self.files()
        with patch.object(recovery,'_records',return_value=[{'state':'complete'}]*256):
            with self.assertRaisesRegex(ValueError,'Límite de copias'):self.apply('snapshot')
        self.assertEqual(self.files(),before)
        self.assertEqual(recovery.config_status(self.root)['backups'],[])
