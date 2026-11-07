from __future__ import annotations

from dataclasses import asdict, replace
from contextlib import redirect_stdout, redirect_stderr
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

from tools.acceptance_lab import prepare_project
from factoria.application.resource_lifecycle import preview_resource, apply_resource, resource_inventory, ResourceConflict
from factoria.application.resource_archive import archive_records
from factoria.application.skill_catalog import SkillDefinition, save_skill, skill_catalog_revision, skill_catalog_snapshot
from factoria.application.agent_profiles import load_agent_profiles, save_agent_profile, AgentRoleProfile
from factoria.application.workflow_presets import load_catalog, save_preset, default_preset
from factoria.application.native_workflow import NativeWorkflow
from factoria.application.project_integration import ProjectIntegration
from factoria.application.project_templates import export_template, preview_template
from factoria.project_cli import run_project_cli
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaWebHandler, FactoriaHTTPServer
from factoria.web_app_n8n import FactoriaN8NHandler


class ResourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'project'
        home=patch('pathlib.Path.home',return_value=self.base/'home');home.start();self.addCleanup(home.stop)
        prepare_project(self.root,'chatgpt-checkout','feature')

    def operate(self, action, kind, identifier=None, **extra):
        request={'action':action,'kind':kind,**extra}
        if identifier is not None:request['id']=identifier
        plan=preview_resource(self.root,request)
        return apply_resource(self.root,request,token=plan['token'],confirmed=True)

    def archive_agent_dependencies(self):
        for identifier in ('fix-lab','feature-lab'):self.operate('archive','workflow',identifier)
        return self.operate('archive','agent','lab-implementer')

    def test_duplicate_every_type_and_basic_resources_preserving_originals(self):
        original=export_template(self.root,'Before')
        for kind,identifier,new_id in [('skill','lab-rules','rules-copy'),('agent','lab-implementer','agent-copy'),('workflow','feature-lab','feature-copy'),('agent','reviewer','review-copy'),('workflow','fix','fix-copy')]:
            result=self.operate('duplicate',kind,identifier,new_id=new_id)
            self.assertTrue(result['applied'])
        skills={s.id:s for s in skill_catalog_snapshot(self.root)[0]}
        self.assertEqual(skills['rules-copy'].content,skills['lab-rules'].content)
        agents={a.role:a for a in load_agent_profiles(self.root)}
        self.assertEqual(agents['agent-copy'].skills,agents['lab-implementer'].skills)
        self.assertEqual(agents['review-copy'].base_role,'reviewer')
        self.assertEqual(load_catalog(self.root)['feature-copy'].steps,load_catalog(self.root)['feature-lab'].steps)
        current=export_template(self.root,'After')
        for value in original['skills']:self.assertIn(value,current['skills'])
        for value in original['agents']:self.assertIn(value,current['agents'])
        for key,value in original['workflows'].items():self.assertEqual(current['workflows'][key],value)

    def test_duplicate_rejects_existing_invalid_reserved_and_foreign_identifiers(self):
        for identifier in ('lab-rules','../bad','con','BadCase'):
            with self.subTest(identifier=identifier),self.assertRaises(ValueError):
                self.operate('duplicate','skill','lab-rules',new_id=identifier)
        foreign=self.root/'.factoria/skills/FOREIGN.md';foreign.write_text('User content')
        with self.assertRaises(ResourceConflict):self.operate('duplicate','skill','lab-rules',new_id='foreign')
        self.assertEqual(foreign.read_text(),'User content')

    def test_archive_blocks_references_including_normalized_skill_paths(self):
        request={'action':'archive','kind':'skill','id':'lab-rules'}
        self.assertIn('agent:lab-implementer',preview_resource(self.root,request)['blockers'])
        with self.assertRaises(ResourceConflict):self.operate('archive','skill','lab-rules')
        self.assertIn('workflow:feature-lab',preview_resource(self.root,{'action':'archive','kind':'agent','id':'lab-implementer'})['blockers'])
        agent=next(a for a in load_agent_profiles(self.root) if a.role=='lab-implementer')
        save_agent_profile(self.root,replace(agent,skills=('.factoria/skills/./lab-rules.md',)))
        self.assertIn('agent:lab-implementer',preview_resource(self.root,request)['blockers'])
        snapshot=self.root/'.factoria/work/frozen/native.json';snapshot.parent.mkdir(parents=True)
        snapshot.write_text(json.dumps({'kind':'fix','definition':{'agents':[{'role':'lab-implementer','skills':['.factoria/skills/./lab-rules.md']}]}}))
        self.assertIn('frozen',preview_resource(self.root,request)['snapshots_preserved'])

    def test_basics_cannot_be_archived(self):
        for kind,identifier in [('agent','reviewer'),('workflow','fix'),('workflow','feature')]:
            with self.subTest(kind=kind),self.assertRaises(ResourceConflict):self.operate('archive',kind,identifier)
        self.assertEqual(archive_records(self.root),{})

    def test_archive_restore_dependencies_and_exact_skill_bytes(self):
        original=(self.root/'.factoria/skills/lab-rules.md').read_bytes()
        workflows=[self.operate('archive','workflow',identifier) for identifier in ('fix-lab','feature-lab')]
        agent=self.operate('archive','agent','lab-implementer')
        skill=self.operate('archive','skill','lab-rules')
        self.assertFalse((self.root/'.factoria/skills/lab-rules.md').exists())
        with self.assertRaises(ValueError):self.operate('restore','workflow',archive_id=workflows[0]['archive_id'])
        with self.assertRaises(ValueError):self.operate('restore','agent',archive_id=agent['archive_id'])
        self.operate('restore','skill',archive_id=skill['archive_id'])
        self.assertEqual((self.root/'.factoria/skills/lab-rules.md').read_bytes(),original)
        self.operate('restore','agent',archive_id=agent['archive_id'])
        for item in workflows:self.operate('restore','workflow',archive_id=item['archive_id'])
        ProjectIntegration(self.root).apply(confirmed=True)
        self.assertTrue(ProjectIntegration(self.root).check()['ready'])
        self.assertTrue(all(r['status']=='restored' and r['restored_at'] for r in archive_records(self.root).values()))

    def test_archived_ids_are_reserved_in_editors_and_template_imports(self):
        data=export_template(self.root,'Before')
        self.archive_agent_dependencies();self.operate('archive','skill','lab-rules')
        with self.assertRaises(ValueError):save_skill(self.root,SkillDefinition('lab-rules','Replacement',content='New'),expected_revision=skill_catalog_revision(self.root),create=True)
        with self.assertRaises(ValueError):save_agent_profile(self.root,AgentRoleProfile('lab-implementer','equilibrado',base_role='implementer',name='Replacement'),mode='create')
        with self.assertRaises(ValueError):save_preset(self.root,replace(default_preset('fix'),id='fix-lab',name='Replacement'),create=True)
        with self.assertRaises(ValueError):preview_template(self.root,data)

    def test_new_references_to_archived_dependencies_fail(self):
        self.archive_agent_dependencies();self.operate('archive','skill','lab-rules')
        with self.assertRaises(ValueError):save_agent_profile(self.root,AgentRoleProfile('new-agent','equilibrado',base_role='implementer',name='New',skills=('.factoria/skills/lab-rules.md',)),mode='create')
        preset=replace(default_preset('fix'),id='new-flow',name='New',steps=tuple(replace(s,agent_id='lab-implementer') if s.name=='implement' else s for s in default_preset('fix').steps))
        with self.assertRaises(ValueError):save_preset(self.root,preset,create=True)

    def test_snapshot_and_execution_history_preserved_after_archive(self):
        from factoria.application.history import LocalExecutionHistoryStore
        native=NativeWorkflow(self.root)
        previous=native.start('fix-lab','Previous cancelled flow','codex')
        native.lifecycle(previous['flow_id'],'cancel',confirmed=True)
        archived=LocalExecutionHistoryStore(self.root).list()
        self.assertEqual(len(archived),1)
        flow=native.start('feature-lab','Existing flow','codex')
        workspace=self.root/'.factoria/work'/flow['flow_id'];before={p.name:p.read_bytes() for p in workspace.iterdir() if p.is_file()}
        history=self.root/'.git/factoria/history';history.mkdir(parents=True,exist_ok=True)
        marker=history/'preserve.txt';marker.write_text('Existing history')
        plan=preview_resource(self.root,{'action':'archive','kind':'workflow','id':'feature-lab'})
        self.assertIn(flow['flow_id'],plan['snapshots_preserved'])
        self.operate('archive','workflow','feature-lab')
        self.assertEqual({p.name:p.read_bytes() for p in workspace.iterdir() if p.is_file()},before)
        self.assertEqual(native.status(flow['flow_id'])['workflow_id'],'feature-lab')
        self.assertEqual(marker.read_text(),'Existing history')
        self.assertEqual(LocalExecutionHistoryStore(self.root).list(),archived)

    def test_tokens_confirmation_concurrency_and_policies(self):
        request={'action':'duplicate','kind':'skill','id':'lab-rules','new_id':'copy'};plan=preview_resource(self.root,request)
        with self.assertRaises(PermissionError):apply_resource(self.root,request,token=plan['token'],confirmed=False)
        with self.assertRaises(ResourceConflict):apply_resource(self.root,{**request,'new_id':'different'},token=plan['token'],confirmed=True)
        def apply():
            try:apply_resource(self.root,request,token=plan['token'],confirmed=True);return 'applied'
            except ResourceConflict:return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertCountEqual(list(pool.map(lambda _:apply(),range(2))),['applied','stale'])
        (self.root/'.factoria/config.toml').write_text('[permissions]\nblocked_actions=["write"]\n')
        with self.assertRaises(PermissionError):self.operate('archive','skill','copy')

    def test_failed_finalize_restores_source_and_preserves_failed_record(self):
        import factoria.application.resource_lifecycle as module
        self.operate('duplicate','skill','lab-rules',new_id='copy')
        original=module._write;failed=False
        def failing(path,content,**kwargs):
            nonlocal failed
            if 'archive' in path.parts and b'"status": "archived"' in content and not failed:
                failed=True;raise OSError('disk failure')
            return original(path,content,**kwargs)
        before=(self.root/'.factoria/skills/copy.md').read_bytes()
        with patch.object(module,'_write',side_effect=failing),self.assertRaises(OSError):self.operate('archive','skill','copy')
        self.assertEqual((self.root/'.factoria/skills/copy.md').read_bytes(),before)
        self.assertIn('failed',[r['status'] for r in archive_records(self.root).values()])

    def test_external_catalog_edit_after_preview_is_not_overwritten(self):
        request={'action':'archive','kind':'workflow','id':'feature-lab'};plan=preview_resource(self.root,request)
        source=self.root/'.factoria/workflows.json';data=json.loads(source.read_text());data['feature-lab']['description']='External';source.write_text(json.dumps(data));before=source.read_bytes()
        with self.assertRaises(ResourceConflict):apply_resource(self.root,request,token=plan['token'],confirmed=True)
        self.assertEqual(source.read_bytes(),before)

    def test_new_active_snapshot_invalidates_impact_preview(self):
        request={'action':'archive','kind':'workflow','id':'feature-lab'};plan=preview_resource(self.root,request)
        NativeWorkflow(self.root).start('feature-lab','New active snapshot','codex')
        with self.assertRaises(ResourceConflict):apply_resource(self.root,request,token=plan['token'],confirmed=True)
        self.assertIn('feature-lab',load_catalog(self.root))

    def test_external_reference_added_during_operation_is_preserved(self):
        self.archive_agent_dependencies()
        # Restore only the agent, leaving it unreferenced initially.
        record_id=next(key for key,r in archive_records(self.root).items() if r['kind']=='agent')
        self.operate('restore','agent',archive_id=record_id)
        import factoria.application.resource_lifecycle as module
        original=module._write; changed=False
        def external(path,content,**kwargs):
            nonlocal changed
            result=original(path,content,**kwargs)
            if 'archive' in path.parts and b'"status": "pending"' in content and not changed:
                changed=True
                target=self.root/'.factoria/workflows.json';data=json.loads(target.read_text())
                preset=replace(default_preset('fix'),id='external',name='External',steps=tuple(replace(s,agent_id='lab-implementer') if s.name=='implement' else s for s in default_preset('fix').steps))
                data['external']=preset.to_mapping();target.write_text(json.dumps(data))
            return result
        with patch.object(module,'_write',side_effect=external),self.assertRaises(ResourceConflict):self.operate('archive','agent','lab-implementer')
        self.assertIn('external',load_catalog(self.root))
        self.assertIn('lab-implementer',{a.role for a in load_agent_profiles(self.root)})

    def test_secret_and_incompatible_restoration_are_blocked(self):
        result=self.operate('archive','workflow','feature-lab')
        self.operate('archive','workflow','fix-lab')
        agent=next(a for a in load_agent_profiles(self.root) if a.role=='lab-implementer')
        save_agent_profile(self.root,replace(agent,base_role='reviewer'))
        with self.assertRaises(ValueError):self.operate('restore','workflow',archive_id=result['archive_id'])
        skill=skill_catalog_snapshot(self.root)[0][0]
        path=self.root/skill.path
        path.write_bytes(path.read_bytes()+('password = "'+'x'*40+'"').encode())
        with self.assertRaisesRegex(ValueError,'secreto'):self.operate('duplicate','skill',skill.id,new_id='secret-copy')

    def test_tampered_archive_and_symlink_paths_are_not_restored(self):
        self.operate('duplicate','skill','lab-rules',new_id='copy')
        result=self.operate('archive','skill','copy')
        path=self.root/'.factoria/archive'/f'{result["archive_id"]}.json';record=json.loads(path.read_text());record['resource']['id']='other';path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):self.operate('restore','skill',archive_id=result['archive_id'])
        with self.assertRaises(ValueError):self.operate('restore','skill',archive_id='../escape')
        outside=self.base/'outside.json';outside.write_bytes(path.read_bytes());path.unlink()
        try:path.symlink_to(outside)
        except OSError:return
        before=outside.read_bytes()
        with self.assertRaises(ValueError):self.operate('restore','skill',archive_id=result['archive_id'])
        self.assertEqual(outside.read_bytes(),before)

    def test_cli_list_preview_confirm_and_read_only(self):
        def cli(*args):
            output=io.StringIO()
            with redirect_stdout(output),redirect_stderr(io.StringIO()):code=run_project_cli(['--project',str(self.root),*args])
            return code,output.getvalue()
        self.assertEqual(cli('project','resources','list')[0],0)
        command=['project','resources','duplicate','agent','reviewer','--new-id','review-copy']
        code,text=cli(*command);self.assertEqual(code,0);token=json.loads(text)['token']
        self.assertEqual(cli('--read-only',*command,'--yes','--token',token)[0],1)
        self.assertEqual(cli(*command,'--yes','--token',token)[0],0)

    def test_both_shells_auth_project_binding_and_api_roundtrip(self):
        UiWorkspaceSettings(self.base,self.root).save()
        for handler in (FactoriaWebHandler,FactoriaN8NHandler):
            server=FactoriaHTTPServer(('127.0.0.1',0),handler);server.factoria_token='test-token'
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_address[1]}'
            def request(action,payload,auth=True):
                req=urllib.request.Request(base+'/api/resource/'+action,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**({'X-Factoria-Token':'test-token'} if auth else {})})
                with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
            try:
                payload={'project_path':str(self.root)}
                with self.assertRaises(urllib.error.HTTPError) as error:request('list',payload,False)
                self.assertEqual(error.exception.code,403)
                oversized=urllib.request.Request(base+'/api/resource/list',data=b'{}',headers={'Content-Type':'application/json','X-Factoria-Token':'test-token','Content-Length':'-1'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(oversized,timeout=5)
                self.assertEqual(error.exception.code,400)
                self.assertTrue(request('list',payload)['active'])
                operation={'action':'duplicate','kind':'skill','id':'lab-rules','new_id':'api-'+handler.__name__.lower()}
                plan=request('preview',{**payload,'request':operation})
                with self.assertRaises(urllib.error.HTTPError) as error:request('apply',{**payload,'project_path':'/another','request':operation,'token':plan['token'],'confirmed':True})
                self.assertEqual(error.exception.code,409)
                self.assertTrue(request('apply',{**payload,'request':operation,'token':plan['token'],'confirmed':True})['applied'])
                with urllib.request.urlopen(base+'/assets/resources.js') as response:self.assertIn(b'resourceApply',response.read())
                with urllib.request.urlopen(base+'/') as response:self.assertIn(b'/assets/resources.js',response.read())
            finally:server.shutdown();server.server_close();thread.join()
