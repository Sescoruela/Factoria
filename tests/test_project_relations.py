from __future__ import annotations

from dataclasses import replace
from contextlib import redirect_stdout, redirect_stderr
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
from factoria.application.project_relations import project_relations
from factoria.application.project_integration import ProjectIntegration
from factoria.application.agent_profiles import save_agent_profile, load_agent_profiles, AgentRoleProfile
from factoria.application.skill_catalog import SkillDefinition, save_skill, skill_catalog_revision
from factoria.application.resource_lifecycle import preview_resource, apply_resource
from factoria.application.workflow_presets import save_preset, default_preset
from factoria.project_cli import run_project_cli
from factoria.ui_workspace import UiWorkspaceSettings
from factoria.web_app import FactoriaHTTPServer, FactoriaWebHandler
from factoria.web_app_n8n import FactoriaN8NHandler


class ProjectRelationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'project'
        home=patch('pathlib.Path.home',return_value=self.base/'home');home.start();self.addCleanup(home.stop)
        prepare_project(self.root,'chatgpt-checkout','feature')

    def nodes(self,graph):return {n['key']:n for n in graph['nodes']}
    def snapshot(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_real_chain_effective_preferences_and_read_only(self):
        before=self.snapshot();graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertEqual(before,self.snapshot())
        self.assertTrue(graph['consistent']);self.assertTrue(graph['integration']['ready'])
        self.assertEqual(graph['diagnostics'],[])
        self.assertIn({'source':'stage:feature-lab:implement','target':'agent:lab-implementer','relation':'uses_agent','enabled':True,'valid':True},graph['edges'])
        self.assertIn({'source':'agent:lab-implementer','target':'skill:.factoria/skills/lab-rules.md','relation':'uses_skill','enabled':True,'valid':True},graph['edges'])
        self.assertEqual(nodes['stage:feature-lab:implement']['profile'],'equilibrado')
        self.assertFalse(nodes['skill:.factoria/skills/lab-rules.md']['orphan'])
        self.assertNotIn('skill_contents',json.dumps(graph));self.assertNotIn('H05-AGENT-LAB',json.dumps(graph))

    def test_orphans_are_reachability_from_allowed_enabled_workflows(self):
        skill=SkillDefinition('unused','Unused',content='No consumer')
        save_skill(self.root,skill,expected_revision=skill_catalog_revision(self.root),create=True)
        save_agent_profile(self.root,AgentRoleProfile('unused-agent','equilibrado',base_role='implementer',name='Unused',skills=(skill.path,)),mode='create')
        graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertTrue(nodes['agent:unused-agent']['orphan']);self.assertTrue(nodes['skill:'+skill.path]['orphan'])
        self.assertEqual(graph['integration']['status'],'stale')
        (self.root/'.factoria/config.toml').write_text('[flows]\nblocked=["fix","feature"]\n')
        graph=project_relations(self.root)
        self.assertTrue(all(not n['enabled'] for n in graph['nodes'] if n['kind']=='workflow'))

    def test_missing_and_incompatible_agent_references_are_partial_not_fatal(self):
        path=self.root/'.factoria/workflows.json';data=json.loads(path.read_text())
        data['feature-lab']['steps'][2]['agent_id']='missing-agent'
        data['fix-lab']['steps'][2]['agent_id']='reviewer'
        path.write_text(json.dumps(data));before=self.snapshot()
        graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertEqual(nodes['agent:missing-agent']['status'],'missing')
        bad=[e for e in graph['edges'] if e['relation']=='uses_agent' and not e['valid']]
        self.assertEqual(len(bad),2);self.assertEqual(graph['integration']['status'],'unavailable')
        self.assertEqual(self.snapshot(),before)

    def test_missing_external_and_normalized_skill_paths(self):
        agent=next(a for a in load_agent_profiles(self.root) if a.role=='lab-implementer')
        (self.root/'rules.md').write_text('External file')
        save_agent_profile(self.root,replace(agent,skills=('.factoria/skills/./lab-rules.md','rules.md')))
        graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertEqual(nodes['skill:rules.md']['status'],'external');self.assertIsNone(nodes['skill:rules.md']['editor'])
        self.assertIn('skill:.factoria/skills/lab-rules.md',nodes)
        (self.root/'rules.md').unlink();graph=project_relations(self.root)
        self.assertEqual(self.nodes(graph)['skill:rules.md']['status'],'missing')
        self.assertTrue(any(d['code']=='broken_skill_reference' for d in graph['diagnostics']))

    def test_archived_references_and_pending_records_are_explicit(self):
        request={'action':'archive','kind':'workflow','id':'feature-lab'};plan=preview_resource(self.root,request)
        result=apply_resource(self.root,request,token=plan['token'],confirmed=True)
        graph=project_relations(self.root)
        self.assertEqual(self.nodes(graph)['workflow:feature-lab']['status'],'archived')
        path=self.root/'.factoria/archive'/f'{result["archive_id"]}.json';record=json.loads(path.read_text());record['status']='pending';path.write_text(json.dumps(record))
        self.assertEqual(self.nodes(project_relations(self.root))['workflow:feature-lab']['status'],'pending')

    def test_bad_json_never_falls_back_to_default_agents(self):
        (self.root/'.factoria/agents.json').write_text('{broken')
        graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertTrue(any(d['code']=='invalid_catalog' for d in graph['diagnostics']))
        self.assertEqual(nodes['agent:implementer']['status'],'unknown')
        self.assertFalse(graph['orphan_analysis_complete'])
        self.assertTrue(all(n['orphan'] is None for n in graph['nodes'] if n['kind']=='skill' and n['status']=='active'))

    def test_invalid_individual_resources_do_not_hide_other_catalogs(self):
        path=self.root/'.factoria/agents.json';data=json.loads(path.read_text());data['lab-implementer']['profile']='invalid';path.write_text(json.dumps(data))
        (self.root/'.factoria/skills/bad.md').write_text('<!-- factoria:skill:v1 -->\nmalformed')
        graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertIn('workflow:feature',nodes);self.assertIn('agent:reviewer',nodes)
        self.assertEqual(nodes['skill:.factoria/skills/bad.md']['status'],'invalid')
        self.assertTrue(any(d['code']=='invalid_agent' for d in graph['diagnostics']))

    def test_disabled_stage_and_profile_tool_override(self):
        preset=default_preset('fix')
        preset=replace(preset,id='custom-fix',name='Custom',steps=tuple(replace(s,profile='rapido',tool='opencode') if s.name=='implement' else s for s in preset.steps))
        save_preset(self.root,preset,create=True)
        graph=project_relations(self.root);nodes=self.nodes(graph)
        self.assertFalse(nodes['stage:custom-fix:plan']['enabled'])
        self.assertEqual(nodes['stage:custom-fix:implement']['profile'],'rapido')
        self.assertEqual(nodes['stage:custom-fix:implement']['tool'],'opencode')

    def test_unsafe_symlinks_and_capture_limits_report_errors_without_reading_target(self):
        outside=self.base/'private';outside.write_text('PRIVATE DATA')
        path=self.root/'.factoria/skills/external.md'
        try:path.symlink_to(outside)
        except OSError:self.skipTest('Symlinks unavailable')
        before=outside.read_bytes();graph=project_relations(self.root)
        self.assertTrue(any(d['code']=='source_unreadable_or_limit' for d in graph['diagnostics']))
        self.assertNotIn('PRIVATE DATA',json.dumps(graph));self.assertEqual(outside.read_bytes(),before)

    def test_source_changes_are_reported_inconsistent_and_never_written(self):
        import factoria.application.project_relations as module
        original=module._capture;calls=0
        def changing(root):
            nonlocal calls
            calls+=1
            if calls==2:(self.root/'.factoria/agents.json').write_text('{}')
            return original(root)
        with patch.object(module,'_capture',side_effect=changing):graph=project_relations(self.root)
        self.assertFalse(graph['consistent']);self.assertIn('source_changed_during_read',[d['code'] for d in graph['diagnostics']])
        self.assertEqual((self.root/'.factoria/agents.json').read_text(),'{}')

    def test_large_sources_are_not_read_or_presented_as_healthy(self):
        path=self.root/'.factoria/skills/huge.md';path.write_bytes(b'x'*(2*1024*1024+1))
        original=Path.read_bytes
        def bounded(file):
            if file==path:raise AssertionError('Oversized source must not be read')
            return original(file)
        with patch.object(Path,'read_bytes',bounded):graph=project_relations(self.root)
        self.assertFalse(graph['orphan_analysis_complete'])
        self.assertIn('source_unreadable_or_limit',[d['code'] for d in graph['diagnostics']])

    def test_revision_changes_for_saved_content_even_if_edges_do_not(self):
        before=project_relations(self.root)
        path=self.root/'.factoria/agents.json';data=json.loads(path.read_text());data['lab-implementer']['instructions']='New private instructions';path.write_text(json.dumps(data))
        after=project_relations(self.root)
        self.assertNotEqual(before['revision'],after['revision']);self.assertEqual(before['edges'],after['edges'])
        self.assertNotIn('New private instructions',json.dumps(after))

    def test_cli_read_only_and_broken_reference_exit_status(self):
        def cli():
            output=io.StringIO()
            with redirect_stdout(output),redirect_stderr(io.StringIO()):code=run_project_cli(['--project',str(self.root),'--read-only','project','relations'])
            return code,output.getvalue()
        code,text=cli();self.assertEqual(code,0);self.assertTrue(json.loads(text)['consistent'])
        (self.root/'.factoria/workflows.json').write_text('{broken')
        self.assertEqual(cli()[0],1)

    def test_both_shells_api_binding_editor_route_and_existing_editor_auth(self):
        UiWorkspaceSettings(self.base,self.root).save()
        for handler in (FactoriaWebHandler,FactoriaN8NHandler):
            server=FactoriaHTTPServer(('127.0.0.1',0),handler);server.factoria_token='test-token'
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_address[1]}'
            def request(payload,auth=True):
                req=urllib.request.Request(base+'/api/project/relations',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**({'X-Factoria-Token':'test-token'} if auth else {})})
                with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
            try:
                with self.assertRaises(urllib.error.HTTPError) as error:request({'project_path':str(self.root)},False)
                self.assertEqual(error.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as error:request({'project_path':'/other'})
                self.assertEqual(error.exception.code,409)
                self.assertTrue(request({'project_path':str(self.root)})['consistent'])
                for url,marker in [('/','/assets/relations.js'),('/editors','/assets/skills.js'),('/assets/relations.js','relationsReload')]:
                    with urllib.request.urlopen(base+url) as response:self.assertIn(marker.encode(),response.read())
                req=urllib.request.Request(base+'/api/state',headers={'X-Factoria-Token':'test-token'})
                with urllib.request.urlopen(req) as response:state=json.load(response)
                self.assertTrue(state['agent_roles'])
                profile=next(a for a in state['agent_roles'] if a['role']=='reviewer')
                body={**profile,'project_path':str(self.root),'revision':state['agent_catalog_revision'],'instructions':'H10 editor bridge test'}
                req=urllib.request.Request(base+'/api/agent-role/save',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
                self.assertEqual(error.exception.code,403)
                req.add_header('X-Factoria-Token','test-token')
                with urllib.request.urlopen(req) as response:state=json.load(response)['state']
                self.assertEqual(next(a for a in state['agent_roles'] if a['role']=='reviewer')['instructions'],'H10 editor bridge test')
                skill=state['skills'][0]
                body={**skill,'project_path':str(self.root),'revision':state['skill_catalog_revision'],'content':'H10 saved skill'}
                req=urllib.request.Request(base+'/api/skill/save',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Factoria-Token':'test-token'})
                with urllib.request.urlopen(req) as response:self.assertEqual(json.load(response)['state']['skills'][0]['content'],'H10 saved skill')
            finally:server.shutdown();server.server_close();thread.join()
