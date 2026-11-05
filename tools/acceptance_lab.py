"""H05 developer lab. Never starts/authenticates a provider or approves a flow."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import replace
from datetime import date
from importlib.metadata import version
from pathlib import Path

from factoria.application.agent_profiles import AgentRoleProfile, save_agent_profile
from factoria.application.history import LocalExecutionHistoryStore
from factoria.application.native_workflow import NativeWorkflow
from factoria.application.project_integration import ProjectIntegration
from factoria.application.skill_catalog import SkillDefinition, save_skill, skill_catalog_revision
from factoria.application.workflow_presets import default_preset, save_preset
from factoria.domain.models import ConfirmedCommand, MemoryMetadata, ProjectKind, ProjectMemory
from factoria.memory.filesystem import write_initial_memory

ENVIRONMENTS = ('codex-cli', 'opencode', 'chatgpt-checkout')
AGENT_MARKER = 'H05-AGENT-LAB'
SKILL_MARKER = 'H05-SKILL-LAB'
BASELINE_TEST = '''import unittest
from app import sum_even

class SumEvenTests(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(sum_even([1, 2, 3, 4]), 6)
    def test_empty(self):
        self.assertEqual(sum_even([]), 0)
    def test_negative_and_zero(self):
        self.assertEqual(sum_even([-4, -3, 0, 2]), -2)

if __name__ == '__main__':
    unittest.main()
'''
FEATURE_CHECK = '''from app import count_even, sum_even
assert count_even([1, 2, 4, -2, 0]) == 4
assert count_even([]) == 0
assert count_even([-3, -2, -1]) == 1
assert sum_even([1, 2, 3, 4]) == 6
print("Feature acceptance: OK")
'''


def git(root: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                          text=True, encoding='utf-8').stdout.strip()


def preflight() -> dict:
    """PATH presence only. No help, version, login or provider command is run."""
    presence = {name: shutil.which(name) is not None for name in ('git', 'python', 'factoria', 'codex', 'opencode')}
    return {'factoria_version': version('factoria'), 'path_presence': presence,
            'provider_sessions_tested': False, 'authenticated': None,
            'acceptance_status': 'pending', 'note': 'Presence is not authentication or acceptance.'}


def prepare_project(root: Path, environment: str, scenario: str, python_command: str = 'python') -> None:
    root.mkdir(parents=True, exist_ok=False)
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'Factoria acceptance fixture')
    git(root, 'config', 'user.email', 'acceptance@example.invalid')
    git(root, 'config', 'commit.gpgsign', 'false')
    (root / '.git/disabled-hooks').mkdir()
    git(root, 'config', 'core.hooksPath', '.git/disabled-hooks')
    (root / '.gitignore').write_text('__pycache__/\n.factoria/security/\n', encoding='utf-8')
    comparison = '!=' if scenario == 'fix' else '=='
    (root / 'app.py').write_text(f'def sum_even(numbers):\n    return sum(number for number in numbers if number % 2 {comparison} 0)\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests/test_app.py').write_text(BASELINE_TEST, encoding='utf-8')
    if scenario == 'feature':
        (root / 'acceptance_feature.py').write_text(FEATURE_CHECK, encoding='utf-8')
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'test: initialize isolated H05 fixture')
    commands = [ConfirmedCommand('test', (python_command, '-m', 'unittest', 'discover', '-s', 'tests', '-v'))]
    if scenario == 'feature':
        commands.append(ConfirmedCommand('test', (python_command, 'acceptance_feature.py')))
    memory = ProjectMemory(
        project_name='H05 acceptance lab', purpose='Validate project configuration in a real coding session.',
        metadata=MemoryMetadata(git(root, 'rev-parse', 'HEAD'), date.today(), version('factoria'), ProjectKind.ACTIVE),
        technologies=('Python 3.11+',), confirmed_check_commands=tuple(commands),
        mandatory_rules=('Do not alter baseline tests or acceptance_feature.py to force a pass.',
                         'Wait for separate human plan/final approval. Never infer it from the initial request.',
                         'Do not launch another LLM through Factoria. Do not push this fixture.'),
        manual_verification=('Check the selected workflow and agent match the requested identifiers.',))
    write_initial_memory(root, memory)
    skill = SkillDefinition('lab-rules', 'Lab implementation rules', 'Configuration retrieval probe',
                            f'Before changing code, record {SKILL_MARKER} in implementation.md.\nPreserve empty-input, zero and negative-integer behaviour. Do not change baseline tests.\n')
    save_skill(root, skill, expected_revision=skill_catalog_revision(root), create=True)
    agent = AgentRoleProfile('lab-implementer', 'equilibrado', instructions=
                             f'Record {AGENT_MARKER} in implementation.md before changing code. Follow the assigned skill and the native workflow. Never approve your own plan or final result.',
                             skills=(skill.path,), base_role='implementer', name='Lab implementer')
    save_agent_profile(root, agent, mode='create')
    for kind in ('fix', 'feature'):
        preset = default_preset(kind)
        preset = replace(preset, id=kind + '-lab', name='Lab ' + kind,
                         steps=tuple(replace(step, agent_id=agent.role) if step.name == 'implement' else step for step in preset.steps))
        save_preset(root, preset, create=True)
    manifest = {'schema_version': 1, 'environment': environment, 'scenario': scenario,
                'expected_workflow': scenario + '-lab', 'factoria_version': version('factoria'),
                'provider_authentication': 'not_tested', 'python_command': python_command}
    (root / '.factoria/h05-lab.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    ProjectIntegration(root).apply(confirmed=True)
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'test: prepare H05 agents skills and workflows')
    baseline = {'commit': git(root, 'rev-parse', 'HEAD')}
    metadata = Path(git(root, 'rev-parse', '--git-path', 'factoria/h05-baseline.json'))
    if not metadata.is_absolute():
        metadata = root / metadata
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(baseline), encoding='utf-8')
    git(root, 'switch', '-c', 'test/h05-' + scenario)


def prepare_lab(destination: Path, python_command: str = 'python') -> dict:
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError('El destino ya existe; usa una carpeta nueva para no sobrescribir datos')
    if any((parent / '.git').exists() for parent in destination.parents):
        raise ValueError('Crea el laboratorio fuera de cualquier repositorio existente')
    if shutil.which('git') is None or shutil.which(python_command) is None:
        raise ValueError('El laboratorio necesita Git y el intérprete Python indicado en PATH')
    destination.mkdir(parents=True, exist_ok=False)
    cases = []
    for environment in ENVIRONMENTS:
        for scenario in ('fix', 'feature'):
            relative = environment + '/' + scenario
            prepare_project(destination / relative, environment, scenario, python_command)
            cases.append({'project': relative, 'environment': environment, 'scenario': scenario,
                          'status': 'pending', 'tool_version': None, 'model': None, 'transcript_refs': [],
                          'observations': {'configuration_loaded': None, 'natural_routing': None,
                                           'explicit_routing': None, 'human_approvals': None,
                                           'blocking_checks': None, 'no_nested_llm': None}})
    report = {'schema_version': 1, 'acceptance_status': 'pending', 'preflight': preflight(), 'cases': cases,
              'without_checkout': {'status': 'pending', 'proposal_only_observed': None, 'transcript_refs': []}}
    (destination / 'acceptance-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (destination / 'README.md').write_text(
        '# H05: repositorios aislados\n\nAbre una sesión nueva en cada carpeta y sigue docs/acceptance/h05-protocol.md del repositorio Factoria.\n'
        'El informe empieza pendiente. No contiene credenciales. No es una prueba superada.\n'
        'Fix: sum_even([1,2,3,4]) devuelve 4; debe devolver 6. Workflow: fix-lab.\n'
        'Feature: añadir count_even(numbers), conservando sum_even. Workflow: feature-lab.\n'
        'El agente debe esperar aprobaciones posteriores del plan y resultado. No las concedas por adelantado.\n', encoding='utf-8')
    return {'created': str(destination), 'projects': len(cases), 'acceptance_status': 'pending'}


def inspect_project(root: Path) -> dict:
    """Inspect recorded artifacts; never turns mechanical checks into human acceptance."""
    root = root.expanduser().resolve()
    manifest = json.loads((root / '.factoria/h05-lab.json').read_text(encoding='utf-8'))
    history = LocalExecutionHistoryStore(root)
    records = history.list(limit=50)
    completed = []
    for record in records:
        raw = record.artifacts.get('native.json')
        if not raw:
            continue
        session = json.loads(raw)
        if record.state == 'completed' and session.get('workflow_id', session['kind']) == manifest['expected_workflow']:
            completed.append((record, session))
    active = []
    observed_session = None
    observed_artifacts = {}
    service = NativeWorkflow(root)
    for execution in service.store.incomplete():
        status = service.status(execution.flow.flow_id)
        active.append({'flow_id': status['flow_id'], 'state': status['state'], 'stage': status['stage'], 'workflow_id': status['workflow_id']})
        if status['workflow_id'] == manifest['expected_workflow']:
            observed_session = json.loads((execution.workspace.root / 'native.json').read_text(encoding='utf-8'))
            observed_artifacts = history.snapshot(execution.workspace.root)
    checks = {'integration_current': ProjectIntegration(root).check()['ready'],
              'working_tree_clean': not git(root, 'status', '--porcelain'), 'completed_flow': bool(completed), 'completed_commit_is_head': False,
              'configured_agent_frozen': False, 'configuration_markers_recorded': False,
              'verification_recorded': False, 'review_recorded': False, 'protected_sources_unchanged': False}
    metadata = Path(git(root, 'rev-parse', '--git-path', 'factoria/h05-baseline.json'))
    if not metadata.is_absolute():
        metadata = root / metadata
    baseline = json.loads(metadata.read_text(encoding='utf-8'))['commit']
    changed = git(root, 'diff', '--name-only', baseline, '--').splitlines()
    protected = lambda path: path == 'AGENTS.md' or path.startswith(('.factoria/', 'docs/memoria/')) or path in {'tests/test_app.py', 'acceptance_feature.py'}
    checks['protected_sources_unchanged'] = not any(protected(path) for path in changed)
    if completed:
        record, observed_session = completed[0]
        observed_artifacts = record.artifacts
        checks['completed_commit_is_head'] = record.commit_sha == git(root, 'rev-parse', 'HEAD')
    if observed_session is not None:
        implementation = observed_artifacts.get('implementation.md', '')
        steps = observed_session['definition']['workflows'][manifest['expected_workflow']]
        checks['configured_agent_frozen'] = any(s['name'] == 'implement' and s.get('agent_id') == 'lab-implementer' for s in steps)
        checks['configuration_markers_recorded'] = AGENT_MARKER in implementation and SKILL_MARKER in implementation
        checks['verification_recorded'] = bool(observed_artifacts.get('verification.md'))
        checks['review_recorded'] = bool(observed_artifacts.get('review.json'))
    return {'environment': manifest['environment'], 'scenario': manifest['scenario'],
            'workflow_id': manifest['expected_workflow'], 'automated_checks': checks, 'active_flows': active,
            'mechanical_result': 'ready_for_human_review' if all(checks.values()) else 'incomplete',
            'provider_authenticated': None, 'tool_version': None, 'model': None,
            'acceptance_status': 'pending_human_review',
            'note': 'Artifacts cannot prove authentication, natural routing, real human approvals or model identity. Attach redacted session evidence.'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('preflight')
    prepare = actions.add_parser('prepare')
    prepare.add_argument('destination', type=Path)
    prepare.add_argument('--python-command', default='python')
    inspect = actions.add_parser('inspect')
    inspect.add_argument('project', type=Path)
    args = parser.parse_args(argv)
    try:
        result = preflight() if args.action == 'preflight' else prepare_lab(args.destination, args.python_command) if args.action == 'prepare' else inspect_project(args.project)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
