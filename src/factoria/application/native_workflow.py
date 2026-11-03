"""Track work performed inside a user's coding-tool session, without nested LLMs."""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import replace
from pathlib import Path

from factoria.application.artifacts import FlowArtifactStore
from factoria.application.execution import SafeCheckExecutor, SubprocessCommandRunner
from factoria.application.flow_service import FlowService
from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.history import LocalExecutionHistoryStore
from factoria.application.impact import ImpactAnalyzer
from factoria.application.policy_runtime import build_execution_context
from factoria.application.project_integration import ProjectIntegration, project_definition, project_path
from factoria.application.review_runtime import parse_structured_review
from factoria.application.state_store import LocalFlowStateStore
from factoria.domain.flow import FlowState
from factoria.config.loader import load_project_config
from factoria.memory.loader import load_project_memory
from factoria.security import SecretScanner
from factoria.security.incidents import SecretIncidentStore

_FILES = {'explore': 'explore.md', 'plan': 'plan.md', 'implement': 'implementation.md',
          'review': 'review.json', 'document': 'memory-proposal.md'}
_INSTRUCTIONS = {
    'explore': 'Leer memoria y código relevante. Documentar causa, alcance y riesgos; para fix incluir reproducción comprobable. No editar código.',
    'plan': 'Escribir criterios verificables, cambios propuestos, riesgos y comprobaciones. No implementar todavía.',
    'approve_plan': 'Mostrar plan.md y esperar aprobación humana explícita antes de --approve-plan.',
    'implement': 'Aplicar solo el trabajo autorizado. Documentar los cambios y evidencia de reproducción en implementation.md. No hacer commit.',
    'verify': 'Ejecutar native next para las comprobaciones confirmadas. Si no hay comandos, mostrar pasos manuales y esperar al usuario.',
    'review': 'Revisar diff, criterios, reglas y verification.md. Escribir el contrato JSON de review. No editar código.',
    'document': 'Proponer cambios de memoria relevantes en memory-proposal.md; no aplicarlos de forma automática.',
    'approve_final': 'Mostrar resultado, verificación y riesgos; esperar aprobación humana explícita antes de --approve-final.',
    'ready_for_commit': 'Mostrar resumen y mensaje propuesto. Esperar autorización para commit; push y PR manuales. Con árbol limpio ejecutar native finish.',
}


class NativeWorkflow:
    def __init__(self, root: Path):
        self.root = root.resolve()
        project_path(self.root, '.factoria/work')
        self.artifacts = FlowArtifactStore(self.root)
        self.store = LocalFlowStateStore(self.artifacts)
        self.service = FlowService(self.artifacts, self.store)

    def _git(self, *args: str) -> str:
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, text=True, encoding='utf-8').stdout.strip()

    def _authorize(self, *, commands: bool = False) -> None:
        context = build_execution_context(self.root, flow_authorized=True)
        governor = ExecutionGovernor()
        governor.assert_allowed(GovernedAction.WRITE, context)
        if commands:
            governor.assert_allowed(GovernedAction.COMMAND, context)

    def _scan(self, extra: tuple[str, ...] = ()) -> None:
        scanner = SecretScanner()
        findings = scanner.scan_files(self.root, (*scanner.changed_paths(self.root), *extra))
        incidents = SecretIncidentStore(self.root)
        incidents.record(findings)
        if incidents.open():
            raise PermissionError('Incidente de secreto abierto; resolver y confirmar rotación antes de continuar')

    def _tree_hash(self) -> str:
        raw = subprocess.run(['git', '-C', str(self.root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                             check=True, capture_output=True).stdout
        result = hashlib.sha256()
        for name in sorted(set(raw.decode('utf-8').split('\0')) - {''}):
            if name.startswith(('.factoria/work/', '.factoria/security/')):
                continue
            path = self.root / name
            if not path.exists() and not path.is_symlink():
                continue
            result.update(b'file\0')
            result.update(name.encode('utf-8') + b'\0')
            result.update(str(path.lstat().st_mode & 0o111).encode('ascii'))
            if path.is_symlink():
                result.update(str(path.readlink()).encode('utf-8'))
            elif path.is_file():
                result.update(path.read_bytes())
        return result.hexdigest()

    def _save(self, flow_id: str, session: dict) -> None:
        path = self.artifacts.workspace(flow_id).root / 'native.json'
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(session, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(path)

    def _load(self, flow_id: str):
        # UUID validation happens before path construction, including for CLI input.
        if str(uuid.UUID(flow_id)) != flow_id:
            raise ValueError('Identificador de flujo no válido')
        project_path(self.root, f'.factoria/work/{flow_id}/state.toml')
        project_path(self.root, f'.factoria/work/{flow_id}/native.json')
        execution = self.store.load(flow_id)
        path = execution.workspace.root / 'native.json'
        session = json.loads(path.read_text(encoding='utf-8'))
        if session.get('flow_id') != flow_id or session.get('schema_version') != 1:
            raise ValueError('Estado nativo incompatible')
        if self._git('branch', '--show-current') != session['branch']:
            raise ValueError('Cambiar explícitamente a la rama del flujo antes de continuar')
        return execution, session

    def start(self, kind: str, task: str, tool: str) -> dict:
        self._authorize()
        if kind not in {'fix', 'feature'} or tool not in {'codex', 'opencode'} or not task.strip():
            raise ValueError('Flujo, plataforma o petición no válidos')
        if SecretScanner().scan_text(task, location='task'):
            raise ValueError('Posible secreto en la petición; no se guarda')
        self._scan()
        if not ProjectIntegration(self.root).check()['ready']:
            raise ValueError('Preparar o regenerar la integración: factoria project prepare --yes')
        definition = project_definition(self.root)
        if kind not in definition['workflows']:
            raise PermissionError('Flujo deshabilitado en este proyecto')
        branch = self._git('branch', '--show-current')
        if not branch or branch in {'main', 'master'}:
            raise ValueError('Seleccionar una rama de trabajo; no se modifica main/master ni detached HEAD')
        if self._git('status', '--porcelain'):
            raise ValueError('El árbol debe estar limpio antes de iniciar el flujo')
        load_project_memory(self.root)
        steps = definition['workflows'][kind]
        sequence = []
        for step in steps:
            if step['name'] == 'review':
                sequence.append('verify')
            sequence.append(step['name'])
            if step['name'] == 'plan':
                sequence.append('approve_plan')
        if kind == 'feature' or 'plan' in sequence:
            sequence.append('approve_final')
        sequence.append('ready_for_commit')
        flow_id = str(uuid.uuid4())
        execution = self.service.start(self.service.create(flow_id=flow_id, kind=kind, label=task))
        session = {'schema_version': 1, 'flow_id': flow_id, 'kind': kind, 'task': task,
                   'tool': tool, 'branch': branch, 'definition': definition, 'sequence': sequence,
                   'index': 0, 'baseline_hash': self._tree_hash(), 'verified_hash': None, 'review_cycles': 0}
        # Freeze confirmed commands/memory together with the configured workflow.
        for name in ('AGENTS.md', 'docs/memoria/testing.md', 'docs/memoria/arquitectura.md', 'docs/memoria/flujos.md', 'docs/memoria/decisiones.md'):
            source = project_path(self.root, name)
            if source.is_file():
                target = execution.workspace.root / 'memory' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
        self.artifacts.write_text(flow_id, 'task.md', task + '\n')
        self._save(flow_id, session)
        return self.status(flow_id)

    def status(self, flow_id: str) -> dict:
        execution, session = self._load(flow_id)
        stage = session['sequence'][session['index']]
        step = next((s for s in session['definition']['workflows'][session['kind']] if s['name'] == stage), None)
        role = next((r for r in session['definition']['agents'] if step and r['role'] == step['role']), None)
        evidence = execution.workspace.root / _FILES[stage] if stage in _FILES else None
        return {'flow_id': flow_id, 'state': execution.flow.state.value, 'stage': stage,
                'tool': session['tool'], 'step': step, 'agent': role,
                'instruction': _INSTRUCTIONS[stage],
                'evidence_file': str(evidence) if evidence else None,
                'manual_steps': session.get('manual_steps', []),
                'external_impact': session.get('external_impact', []),
                'model_selection': 'Seleccionar el perfil en la herramienta; Factoría no cambia el modelo de una sesión externa.'}

    def next(self, flow_id: str, *, approve_plan: bool = False, approve_final: bool = False,
             confirm_manual: bool = False, confirm_external_impact: bool = False, tool: str | None = None) -> dict:
        self._authorize()
        execution, session = self._load(flow_id)
        if execution.flow.state is not FlowState.ACTIVE:
            raise ValueError('Reanudar el flujo antes de avanzar')
        stage = session['sequence'][session['index']]
        config = load_project_config(self.root / '.factoria/config.toml')
        if session['kind'] in config.blocked_flows or (config.allowed_flows and session['kind'] not in config.allowed_flows):
            raise PermissionError('Flujo deshabilitado en la configuración actual')
        if (approve_plan and stage != 'approve_plan') or (approve_final and stage != 'approve_final') or ((confirm_manual or confirm_external_impact) and stage != 'verify'):
            raise ValueError('La aprobación no corresponde a la etapa actual')
        if tool is not None:
            if tool not in {'codex', 'opencode'}:
                raise ValueError('Plataforma no válida')
            session['tool'] = tool
        step = next((s for s in session['definition']['workflows'][session['kind']] if s['name'] == stage), None)
        if step and step['preferred_tool'] and step['preferred_tool'] != session['tool']:
            raise ValueError('Esta etapa requiere ' + step['preferred_tool'] + '; continuar allí con --tool')
        extra = tuple(p.relative_to(self.root).as_posix() for p in execution.workspace.root.glob('*') if p.is_file())
        self._scan(extra)
        memory = load_project_memory(execution.workspace.root / 'memory')
        if stage in {'explore', 'plan'} and self._tree_hash() != session['baseline_hash']:
            raise ValueError('El código cambió durante análisis/planificación; cancelar y revisar el alcance')
        if stage in _FILES:
            evidence = project_path(self.root, (execution.workspace.root / _FILES[stage]).relative_to(self.root).as_posix())
            if not evidence.is_file() or not evidence.read_text(encoding='utf-8').strip():
                raise ValueError('Falta evidencia de la etapa: ' + _FILES[stage])
        if stage == 'plan':
            session['plan_hash'] = hashlib.sha256((execution.workspace.root / 'plan.md').read_bytes()).hexdigest()
        if stage == 'approve_plan':
            if not approve_plan:
                raise PermissionError('Esperando aprobación humana del plan: --approve-plan')
            current_plan = hashlib.sha256((execution.workspace.root / 'plan.md').read_bytes()).hexdigest()
            if current_plan != session['plan_hash'] or self._tree_hash() != session['baseline_hash']:
                raise ValueError('El plan o el código cambiaron; revisar antes de aprobar')
        if stage == 'implement' and session['kind'] == 'fix' and 'plan' not in session['sequence']:
            paths = SecretScanner.changed_paths(self.root)
            stats = self._git('diff', '--numstat', 'HEAD')
            lines = sum(int(v) for line in stats.splitlines() for v in line.split('\t')[:2] if v.isdigit())
            for name in self._git('ls-files', '--others', '--exclude-standard').splitlines():
                path = self.root / name
                if path.is_file() and not path.is_symlink():
                    lines += len(path.read_bytes().splitlines())
            has_tests = bool(memory.confirmed_check_commands or memory.confirmed_commands)
            impact = ImpactAnalyzer().analyze(memory, paths)
            sensitive = any(Path(p).name in {'web.config', 'package.json', 'pyproject.toml'} or 'migration' in p.lower() for p in paths)
            if len(paths) > (3 if has_tests else 2) or lines > (80 if has_tests else 40) or impact.contract_impacts or sensitive:
                raise ValueError('La corrección supera el alcance pequeño; cancelar conservando código y replantear con etapa plan activada')
        if stage == 'verify':
            self._authorize(commands=True)
            executor = SafeCheckExecutor(SubprocessCommandRunner())
            changed = SecretScanner.changed_paths(self.root)
            plan = executor.plan(memory, changed_files=changed)
            if plan.commands:
                attempts = session.get('verification_attempts', 0)
                if attempts >= 3:
                    raise ValueError('Límite de tres verificaciones alcanzado; cancelar y replantear')
                session['verification_attempts'] = attempts + 1
                self._save(flow_id, session)
            summary = executor.execute(memory, project_root=self.root, changed_files=changed)
            self.artifacts.write_text(flow_id, 'verification.md', '\n'.join(
                f"- {'PASS' if e.passed else 'FAIL'} {e.name}\n{e.stdout}\n{e.stderr}" for e in summary.executions)
                or 'No confirmed automated checks selected.\n')
            if summary.secret_findings:
                SecretIncidentStore(self.root).record(summary.secret_findings)
                raise PermissionError('Secreto detectado en la verificación; flujo bloqueado')
            if any(not e.passed and e.required for e in summary.executions):
                raise ValueError('Verificación obligatoria fallida; corregir y volver a ejecutar native next')
            if not summary.executions:
                if not memory.manual_verification:
                    raise ValueError('No hay comandos ni pasos manuales confirmados; completar la memoria')
                session['manual_steps'] = list(memory.manual_verification)
                self._save(flow_id, session)
                if not confirm_manual:
                    raise PermissionError('Esperando comprobación humana: consultar native status y usar --confirm-manual')
                self.artifacts.write_text(flow_id, 'manual-verification.json', json.dumps({'confirmed': True, 'steps': list(memory.manual_verification)}))
            impact = ImpactAnalyzer().analyze(memory, changed)
            self.artifacts.write_text(flow_id, 'impact.md', ImpactAnalyzer.render(impact))
            session['external_impact'] = [item.name for item in impact.external_impacts]
            self._save(flow_id, session)
            if impact.blocking:
                if not confirm_external_impact:
                    raise PermissionError('Revisión humana de consumidores externos requerida: --confirm-external-impact')
                self.artifacts.write_text(flow_id, 'external-impact-review.json', json.dumps({'confirmed': True, 'consumers': session['external_impact']}))
            session['verified_hash'] = self._tree_hash()
        if stage in {'review', 'document', 'approve_final', 'ready_for_commit'}:
            if self._tree_hash() != session['verified_hash']:
                raise ValueError('El código cambió después de verificar; ejecutar native retry para repetir verificación y review')
        if stage == 'review':
            review = parse_structured_review((execution.workspace.root / 'review.json').read_text(encoding='utf-8'))
            if review.blocks_closure:
                raise ValueError('Review bloqueante; corregir y ejecutar native retry')
        if stage == 'approve_final' and not approve_final:
            raise PermissionError('Esperando aprobación humana final: --approve-final')
        if stage == 'ready_for_commit':
            raise ValueError('Tras commit explícito y árbol limpio usar native finish')
        session['index'] += 1
        self._save(flow_id, session)
        return self.status(flow_id)

    def retry(self, flow_id: str) -> dict:
        self._authorize()
        execution, session = self._load(flow_id)
        if execution.flow.state is not FlowState.ACTIVE or session['index'] < session['sequence'].index('verify'):
            raise ValueError('Solo se repite verificación después de implementar')
        if session['review_cycles'] >= 2:
            raise ValueError('Límite de dos ciclos de corrección alcanzado; cancelar y replantear')
        session['review_cycles'] += 1
        session['index'] = session['sequence'].index('verify')
        session['verified_hash'] = None
        review = execution.workspace.root / 'review.json'
        if review.exists():
            review.rename(execution.workspace.root / f"review-cycle-{session['review_cycles']}.json")
        self._save(flow_id, session)
        return self.status(flow_id)

    def lifecycle(self, flow_id: str, action: str, *, confirmed: bool = False) -> dict:
        self._authorize()
        execution, session = self._load(flow_id)
        if action in {'pause', 'resume'}:
            getattr(self.service, action)(execution)
            return self.status(flow_id)
        if action == 'finish':
            self._scan()
            if execution.flow.state is not FlowState.ACTIVE or session['sequence'][session['index']] != 'ready_for_commit':
                raise ValueError('Completar todas las etapas antes de cerrar')
            if self._git('status', '--porcelain') or self._tree_hash() != session['verified_hash']:
                raise ValueError('Cerrar requiere árbol limpio con el contenido verificado')
            target = FlowState.COMPLETED
        elif action == 'cancel':
            if not confirmed:
                raise PermissionError('Cancelar requiere --yes; conserva código y rama')
            target = FlowState.CANCELLED
        else:
            raise ValueError('Acción desconocida')
        terminal = replace(execution, flow=execution.flow.transition(target))
        history = LocalExecutionHistoryStore(self.root)
        snapshot = history.snapshot(execution.workspace.root)
        snapshot['native.json'] = json.dumps(session, ensure_ascii=False)
        history.archive(terminal, artifacts=snapshot, branch=session['branch'], commit_sha=self._git('rev-parse', 'HEAD'))
        self.artifacts.cleanup(flow_id)
        return {'flow_id': flow_id, 'state': target.value, 'code_preserved': True, 'branch_preserved': True}
