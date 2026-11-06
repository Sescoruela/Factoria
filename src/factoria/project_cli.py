from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from factoria.application.native_workflow import NativeWorkflow
from factoria.application.project_integration import ProjectIntegration


def run_project_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='factoria')
    parser.add_argument('--project', default='.')
    parser.add_argument('--read-only', action='store_true')
    parser.add_argument('--profile', choices=('safe', 'normal', 'power'))
    group = parser.add_subparsers(dest='command', required=True)
    project = group.add_parser('project').add_subparsers(dest='action', required=True)
    prepare = project.add_parser('prepare', help='Preview or generate shared configuration for Codex and OpenCode')
    prepare.add_argument('--yes', action='store_true')
    project.add_parser('check', help='Check freshness and ownership without calling an LLM')
    project.add_parser('workflows', help='List configured workflow identifiers and base types')
    templates = project.add_parser('templates', help='Export or preview/import portable project resources').add_subparsers(dest='template_action', required=True)
    export = templates.add_parser('export')
    export.add_argument('--name', required=True)
    export.add_argument('--output', type=Path)
    importing = templates.add_parser('import')
    importing.add_argument('file', type=Path)
    importing.add_argument('--yes', action='store_true')
    importing.add_argument('--token', help='Token returned by the reviewed preview')
    native = group.add_parser('native').add_subparsers(dest='action', required=True)
    start = native.add_parser('start')
    start.add_argument('kind', help='Identificador del workflow: fix, feature o uno propio del catálogo')
    start.add_argument('--task', required=True)
    start.add_argument('--tool', choices=('codex', 'opencode'), required=True)
    for name in ('next', 'status', 'pause', 'resume', 'retry', 'finish', 'cancel'):
        command = native.add_parser(name)
        command.add_argument('flow_id')
        if name == 'next':
            command.add_argument('--approve-plan', action='store_true')
            command.add_argument('--approve-final', action='store_true')
            command.add_argument('--confirm-manual', action='store_true')
            command.add_argument('--confirm-external-impact', action='store_true')
            command.add_argument('--tool', choices=('codex', 'opencode'))
        if name == 'cancel':
            command.add_argument('--yes', action='store_true')
    args = parser.parse_args(argv)
    try:
        root = Path(args.project).expanduser().resolve()
        located = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                                 capture_output=True, text=True, encoding='utf-8')
        if located.returncode != 0:
            raise ValueError('Selecciona una carpeta dentro de un repositorio Git')
        root = Path(located.stdout.strip()).resolve()
        if args.profile:
            raise ValueError('El modo directo usa la política del proyecto; no cambia perfiles por ejecución')
        if args.read_only and args.command == 'project' and args.action == 'templates' and getattr(args, 'output', None):
            raise PermissionError('Modo solo lectura: exportar a archivo está bloqueado')
        if args.read_only and not (args.command == 'project' and (args.action in {'check', 'workflows'} or not getattr(args, 'yes', False))) and not (args.command == 'native' and args.action == 'status'):
            raise PermissionError('Modo solo lectura: operación bloqueada')
        if args.command == 'project':
            if args.action == 'templates':
                from factoria.application.project_templates import export_template, read_template, preview_template, apply_template
                if args.template_action == 'export':
                    result = export_template(root, args.name)
                    if args.output:
                        from factoria.application.governance import ExecutionGovernor, GovernedAction
                        from factoria.application.policy_runtime import build_execution_context
                        ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(root))
                        with args.output.open('xb') as stream:
                            stream.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
                        result = {'exported': str(args.output)}
                else:
                    data = read_template(args.file)
                    result = (apply_template(root, data, expected_token=args.token, confirmed=True)
                              if args.yes else preview_template(root, data))
                print(json.dumps(result, ensure_ascii=True, indent=2))
                return 1 if result.get('conflicts') else 0
            service = ProjectIntegration(root)
            if args.action == 'workflows':
                from factoria.application.workflow_presets import load_catalog
                result = {'workflows': [{'id': item.identifier, 'name': item.name or item.identifier, 'kind': item.kind, 'description': item.description}
                                        for item in load_catalog(root).values()]}
                print(json.dumps(result, ensure_ascii=True, indent=2))
                return 0
            if args.action == 'check':
                result = service.check()
                print(json.dumps(result, ensure_ascii=True, indent=2))
                return 0 if result['ready'] else 1
            plan = service.apply(confirmed=True) if args.yes else service.plan()
            result = {'applied': args.yes, 'changed': plan.changed, 'conflicts': plan.conflicts,
                      'next': 'Guardar los cambios del proyecto en Git y abrir Codex u OpenCode.'}
        else:
            workflow = NativeWorkflow(root)
            if args.action == 'start':
                result = workflow.start(args.kind, args.task, args.tool)
            elif args.action == 'next':
                result = workflow.next(args.flow_id, approve_plan=args.approve_plan, approve_final=args.approve_final,
                                       confirm_manual=args.confirm_manual, confirm_external_impact=args.confirm_external_impact, tool=args.tool)
            elif args.action in {'status', 'retry'}:
                result = getattr(workflow, args.action)(args.flow_id)
            else:
                result = workflow.lifecycle(args.flow_id, args.action, confirmed=getattr(args, 'yes', False))
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1
