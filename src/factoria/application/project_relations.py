"""Read-only, bounded and partial diagnostics of real project relationships."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tomllib

from factoria.application.agent_profiles import default_agent_profiles, AgentRoleProfile, validate_agent_profile
from factoria.application.workflow_presets import default_preset, VisualWorkflowPreset, VisualWorkflowStep, validate_preset, workflow_allowed
from factoria.application.project_integration import project_path, ProjectIntegration
from factoria.application.project_templates import _locks, _json
from factoria.application.resource_archive import archive_records
from factoria.application.skill_catalog import decode_skill_text
from factoria.config.loader import project_config_from_mapping


def _capture(root):
    names={'.factoria/agents.json','.factoria/ui-agents.json','.factoria/workflows.json',
           '.factoria/ui-workflows.json','.factoria/config.toml','AGENTS.md'}
    problems=[]
    for folder,suffix in (('.factoria/skills','.md'),('.factoria/archive','.json'),('docs/memoria','.md')):
        try:
            directory=project_path(root,folder)
            if directory.exists():
                if not directory.is_dir():raise ValueError('not_directory')
                entries=list(directory.iterdir())
                if len(entries)>2048:raise ValueError('too_many_files')
                names.update(p.relative_to(root).as_posix() for p in entries if p.suffix.lower()==suffix)
        except (ValueError,OSError):problems.append(folder)
    data={};total=0
    for name in sorted(names):
        try:
            path=project_path(root,name)
            if path.exists():
                if not path.is_file() or path.stat().st_size>2*1024*1024:raise ValueError('large_or_invalid_file')
                total+=path.stat().st_size
                if total>8*1024*1024:raise ValueError('capture_limit')
                data[name]=path.read_bytes()
            else:data[name]=None
        except (ValueError,OSError):problems.append(name)
    digest=hashlib.sha256(_json([{key:None if value is None else hashlib.sha256(value).hexdigest() for key,value in data.items()},sorted(problems)])).hexdigest()
    return data,sorted(set(problems)),digest


def project_relations(root: Path) -> dict:
    root=root.resolve()
    with _locks():
        sources,problems,before=_capture(root)
        nodes={};edges=[];diagnostics=[];external_checks={}
        def issue(code,subject,severity='error'):
            diagnostics.append({'code':code,'subject':subject,'severity':severity})
        for problem in problems:issue('source_unreadable_or_limit',problem)
        def node(key,kind,label,**extra):
            nodes[key]={'key':key,'kind':kind,'label':label,'status':'active',**extra}
            return key
        def raw_catalog(current,legacy):
            name=current if sources.get(current) is not None or current in problems else legacy
            if name in problems:return None
            if sources.get(name) is None:return {}
            try:
                data=json.loads(sources[name])
                if not isinstance(data,dict):raise ValueError('mapping_required')
                return data
            except (ValueError,UnicodeError):issue('invalid_catalog',name);return None
        records={}
        try:
            if any(p.startswith('.factoria/archive') for p in problems):raise ValueError('archive_unreadable')
            records=archive_records(root)
        except (ValueError,OSError):issue('invalid_archive','.factoria/archive')
        reserved={}
        for record_id,record in records.items():
            if record['status'] in ('archived','pending') or record.get('recovery_required'):
                reserved[(record['kind'],record['id'])]=(record_id,record['status'])
        profile_data=raw_catalog('.factoria/agents.json','.factoria/ui-agents.json')
        agents={a.role:a for a in default_agent_profiles()} if profile_data is not None else {}
        for identifier,value in (profile_data or {}).items():
            agents.pop(identifier,None)
            try:
                if not isinstance(value,dict):raise ValueError('invalid_agent')
                agents[identifier]=validate_agent_profile(AgentRoleProfile.from_mapping({**value,'role':identifier}))
            except ValueError:issue('invalid_agent',f'agent:{identifier}')
        for identifier,agent in agents.items():
            status=reserved.get(('agent',identifier),(None,'active'))[1]
            node(f'agent:{identifier}','agent',agent.name or identifier,id=identifier,role=agent.base_role or agent.role,
                 profile=agent.profile,tool=agent.platform,status=status,editor={'kind':'agent','id':identifier} if status=='active' else None)
        for name,content in sources.items():
            if not name.startswith('.factoria/skills/') or content is None:continue
            try:
                skill=decode_skill_text(content.decode('utf-8'),Path(name).name)
                identifier=skill.id if skill else Path(name).stem
                status=reserved.get(('skill',identifier),(None,'active'))[1]
                node('skill:'+name,'skill',skill.name if skill else name,id=identifier,path=name,managed=skill is not None,
                     status=status if skill else 'external',editor={'kind':'skill','id':identifier} if skill and status=='active' else None)
            except (ValueError,OSError):node('skill:'+name,'skill',name,path=name,status='invalid',editor=None);issue('invalid_skill',name)
        for (kind,identifier),(record_id,status) in reserved.items():
            key='skill:'+f'.factoria/skills/{identifier}.md' if kind=='skill' else f'{kind}:{identifier}'
            if key in nodes:issue('reserved_resource_present',key)
            else:node(key,kind,identifier,id=identifier,status=status,editor=None,archive_id=record_id)
        for identifier,agent in agents.items():
            source='agent:'+identifier
            for reference in agent.skills:
                try:
                    path=project_path(root,reference);relative=path.relative_to(root).as_posix();key='skill:'+relative
                    if key not in nodes:
                        exists=path.is_file()
                        external_checks[relative]=exists
                        node(key,'skill',relative,path=relative,status='external' if exists else 'missing',managed=False,editor=None)
                    valid=nodes[key]['status'] in ('active','external')
                    if not valid:issue('broken_skill_reference',source+' -> '+key)
                    edges.append({'source':source,'target':key,'relation':'uses_skill','enabled':True,'valid':valid})
                except (ValueError,OSError):issue('unsafe_skill_reference',source)
        flow_data=raw_catalog('.factoria/workflows.json','.factoria/ui-workflows.json')
        presets={key:default_preset(key) for key in ('fix','feature')} if flow_data is not None else {}
        for identifier,value in (flow_data or {}).items():
            presets.pop(identifier,None)
            try:
                if not isinstance(value,dict) or not isinstance(value.get('steps'),list) or any(not isinstance(s,dict) for s in value['steps']):raise ValueError('invalid_workflow')
                builtin=identifier in ('fix','feature')
                if value.get('id') not in (None,identifier) or (builtin and value.get('kind',identifier)!=identifier):raise ValueError('inconsistent_id')
                presets[identifier]=validate_preset(VisualWorkflowPreset(value.get('kind',identifier if builtin else None),
                    tuple(VisualWorkflowStep.from_mapping(s) for s in value['steps']),id=None if builtin else identifier,
                    name=value.get('name',''),description=value.get('description','')))
            except (ValueError,TypeError):issue('invalid_workflow','workflow:'+identifier)
        config=None
        if '.factoria/config.toml' not in problems:
            try:config=project_config_from_mapping(tomllib.loads((sources.get('.factoria/config.toml') or b'').decode('utf-8')))
            except (ValueError,UnicodeError):issue('invalid_policy','.factoria/config.toml')
        for identifier,preset in presets.items():
            key='workflow:'+identifier
            status=reserved.get(('workflow',identifier),(None,'active'))[1]
            enabled=status=='active' and config is not None and workflow_allowed(config,identifier,preset.kind)
            node(key,'workflow',preset.name or identifier,id=identifier,base=preset.kind,status=status,enabled=enabled,
                 editor={'kind':'workflow','id':identifier} if status=='active' else None)
            for index,step in enumerate(preset.steps):
                stage=f'stage:{identifier}:{step.name}';agent_key='agent:'+(step.agent_id or step.role)
                assigned=agents.get(step.agent_id or step.role)
                node(stage,'stage',step.name,workflow_id=identifier,role=step.role,enabled=enabled and step.enabled,
                     profile=step.profile or (assigned.profile if assigned else None),
                     tool=step.tool or (assigned.platform if assigned else None),
                     editor={'kind':'workflow','id':identifier},order=index+1)
                if agent_key not in nodes:
                    node(agent_key,'agent',step.agent_id or step.role,id=step.agent_id or step.role,
                         status='unknown' if profile_data is None else 'missing',editor=None)
                valid=nodes[agent_key]['status']=='active' and nodes[agent_key].get('role')==step.role
                if not valid:issue('broken_or_incompatible_agent_reference',stage+' -> '+agent_key)
                edges.extend([{'source':key,'target':stage,'relation':'has_stage','enabled':enabled and step.enabled,'valid':True},
                              {'source':stage,'target':agent_key,'relation':'uses_agent','enabled':enabled and step.enabled,'valid':valid}])
        reachable={key for key,value in nodes.items() if value['kind']=='workflow' and value.get('enabled')}
        while True:
            following={edge['target'] for edge in edges if edge['source'] in reachable and edge['enabled'] and edge['valid']}
            if following<=reachable:break
            reachable.update(following)
        orphan_complete=(not problems and profile_data is not None and flow_data is not None and config is not None
                         and not any(d['code'] in ('invalid_catalog','invalid_agent','invalid_workflow','invalid_skill','invalid_archive') for d in diagnostics))
        for key,value in nodes.items():
            candidate=value['kind'] in ('agent','skill') and value['status'] in ('active','external')
            value['orphan']=(key not in reachable) if candidate and orphan_complete else (None if candidate else False)
            if value['orphan']:issue('unreachable_resource',key,'warning')
        try:
            if problems or any(d['severity']=='error' for d in diagnostics):raise ValueError('invalid_configuration')
            checked=ProjectIntegration(root).check()
            integration={'status':'current' if checked['ready'] else 'stale','ready':checked['ready'],
                         'changed':checked['changed'],'conflicts':checked['conflicts']}
        except (ValueError,OSError,RuntimeError):
            integration={'status':'unavailable','ready':False};issue('integration_unavailable','integration','warning')
        _,_,after=_capture(root);consistent=before==after
        for relative,existed in external_checks.items():
            try:consistent=consistent and project_path(root,relative).is_file()==existed
            except (ValueError,OSError):consistent=False
        if not consistent:issue('source_changed_during_read','project')
        return {'project_path':str(root),'nodes':list(nodes.values()),'edges':edges,'diagnostics':diagnostics,
                'integration':integration,'consistent':consistent,'orphan_analysis_complete':orphan_complete,
                'revision':hashlib.sha256(_json([before,integration])).hexdigest()}
