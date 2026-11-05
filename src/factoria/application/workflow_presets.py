from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factoria.application.agent_profiles import agent_catalog_revision, load_agent_profiles
from factoria.orchestration import AgentRole, AgentStep, AgentWorkflow, AgentWorkflowPlanner, ModelProfile

_PRESET_FILE = Path('.factoria') / 'workflows.json'
_LEGACY_PRESET_FILE = Path('.factoria') / 'ui-workflows.json'
_CANONICAL_ORDER = ('explore', 'plan', 'implement', 'review', 'document')
_ROLE_BY_NAME = {
    'explore': AgentRole.EXPLORER,
    'plan': AgentRole.PLANNER,
    'implement': AgentRole.IMPLEMENTER,
    'review': AgentRole.REVIEWER,
    'document': AgentRole.DOCUMENTER,
}
_REQUIRED_FEATURE = frozenset(_CANONICAL_ORDER)
_REQUIRED_FIX = frozenset({'explore', 'implement', 'review'})
_OPTIONAL_FIX = frozenset({'plan', 'document'})
_ALLOWED_PLATFORMS = {None, '', 'codex', 'opencode'}
_WORKFLOW_LOCK = threading.RLock()


class WorkflowCatalogConflict(ValueError):
    """An editor is trying to save an obsolete workflow catalog."""


@dataclass(frozen=True, slots=True)
class VisualWorkflowStep:
    name: str
    role: str
    profile: str | None = None
    tool: str | None = None
    enabled: bool = True
    agent_id: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> 'VisualWorkflowStep':
        if not isinstance(data.get('enabled', True), bool):
            raise ValueError('enabled debe ser booleano')
        if data.get('agent_id') is not None and not isinstance(data['agent_id'], str):
            raise ValueError('agent_id debe ser un identificador de texto o null')
        return cls(
            name=str(data.get('name', '')),
            role=str(data.get('role', '')),
            profile=str(data['profile']) if data.get('profile') else None,
            tool=str(data['tool']) if data.get('tool') else None,
            enabled=bool(data.get('enabled', True)),
            agent_id=data.get('agent_id'),
        )


@dataclass(frozen=True, slots=True)
class VisualWorkflowPreset:
    kind: str
    steps: tuple[VisualWorkflowStep, ...]

    def to_mapping(self) -> dict[str, Any]:
        return {'kind': self.kind, 'steps': [asdict(step) for step in self.steps]}


def default_preset(kind: str, *, large_fix: bool = False, update_memory: bool = False) -> VisualWorkflowPreset:
    if kind == 'feature':
        workflow = AgentWorkflowPlanner.feature()
        return VisualWorkflowPreset(
            kind=kind,
            steps=tuple(
                VisualWorkflowStep(
                    name=step.name,
                    role=step.role.value,
                    profile=None,
                    enabled=True,
                )
                for step in workflow.steps
            ),
        )
    if kind == 'fix':
        return VisualWorkflowPreset(
            kind='fix',
            steps=(
                VisualWorkflowStep('explore', AgentRole.EXPLORER.value, enabled=True),
                VisualWorkflowStep('plan', AgentRole.PLANNER.value, enabled=large_fix),
                VisualWorkflowStep('implement', AgentRole.IMPLEMENTER.value, enabled=True),
                VisualWorkflowStep('review', AgentRole.REVIEWER.value, enabled=True),
                VisualWorkflowStep('document', AgentRole.DOCUMENTER.value, enabled=update_memory),
            ),
        )
    raise ValueError(f'Unsupported workflow kind: {kind}')


def validate_preset(preset: VisualWorkflowPreset) -> VisualWorkflowPreset:
    if preset.kind not in {'feature', 'fix'}:
        raise ValueError('El tipo de flujo debe ser feature o fix')
    names = [step.name for step in preset.steps]
    if len(names) != len(set(names)):
        raise ValueError('No puede haber etapas duplicadas en el flujo')
    unknown = [name for name in names if name not in _ROLE_BY_NAME]
    if unknown:
        raise ValueError('Etapa no soportada: ' + ', '.join(unknown))

    normalized: list[VisualWorkflowStep] = []
    for step in preset.steps:
        expected_role = _ROLE_BY_NAME[step.name].value
        if step.role != expected_role:
            raise ValueError(f'La etapa {step.name} debe usar el agente {expected_role}')
        if step.agent_id is not None and (not isinstance(step.agent_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', step.agent_id)):
            raise ValueError(f'Identificador de agente no válido para {step.name}')
        if step.profile is not None:
            try:
                ModelProfile(step.profile)
            except ValueError as exc:
                raise ValueError(f'Perfil no válido para {step.name}: {step.profile}') from exc
        if step.tool not in _ALLOWED_PLATFORMS:
            raise ValueError(f'Plataforma no válida para {step.name}: {step.tool}')
        normalized.append(
            VisualWorkflowStep(
                name=step.name,
                role=step.role,
                profile=step.profile,
                tool=step.tool or None,
                enabled=step.enabled,
                agent_id=step.agent_id,
            )
        )

    enabled_names = [step.name for step in normalized if step.enabled]
    required = _REQUIRED_FEATURE if preset.kind == 'feature' else _REQUIRED_FIX
    missing = sorted(required.difference(enabled_names))
    if missing:
        raise ValueError('No se pueden desactivar etapas obligatorias: ' + ', '.join(missing))
    if preset.kind == 'feature' and set(enabled_names) != _REQUIRED_FEATURE:
        raise ValueError('Una feature debe conservar explore, plan, implement, review y document')
    if preset.kind == 'fix':
        allowed = _REQUIRED_FIX | _OPTIONAL_FIX
        if any(name not in allowed for name in enabled_names):
            raise ValueError('El flujo fix contiene etapas no permitidas')

    order_index = {name: index for index, name in enumerate(_CANONICAL_ORDER)}
    indexes = [order_index[name] for name in enabled_names]
    if indexes != sorted(indexes):
        raise ValueError(
            'El orden solicitado no es seguro. Mantén explore → plan → implement → review → document; '
            'puedes personalizar la plataforma, el perfil y las etapas opcionales.'
        )
    return VisualWorkflowPreset(kind=preset.kind, steps=tuple(normalized))


def validate_assignments(preset: VisualWorkflowPreset, profiles) -> VisualWorkflowPreset:
    checked = validate_preset(preset)
    agents = {agent.role: agent for agent in profiles}
    for step in checked.steps:
        identifier = step.agent_id or step.role
        agent = agents.get(identifier)
        if agent is None:
            raise ValueError(f'El agente {identifier} de {step.name} no existe en el catálogo')
        if (agent.base_role or agent.role) != step.role:
            raise ValueError(f'El agente {identifier} no es compatible con el rol {step.role} de {step.name}')
    return checked


def load_preset(project_root: Path, kind: str, *, large_fix: bool = False, update_memory: bool = False, validate_agents: bool = True) -> VisualWorkflowPreset:
    fallback = default_preset(kind, large_fix=large_fix, update_memory=update_memory)
    from factoria.application.project_integration import project_path
    path = project_path(project_root, _PRESET_FILE.as_posix())
    if not path.exists():
        path = project_path(project_root, _LEGACY_PRESET_FILE.as_posix())
    if not path.exists():
        return fallback
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('La configuración de flujos no es válida') from exc
    if not isinstance(raw, dict):
        raise ValueError('La configuración de flujos debe ser un objeto')
    entry = raw.get(kind)
    if entry is None:
        return fallback
    if not isinstance(entry, dict):
        raise ValueError('La configuración del flujo debe ser un objeto')
    raw_steps = entry.get('steps')
    if not isinstance(raw_steps, list):
        raise ValueError('Las etapas deben ser una lista')
    if any(not isinstance(item, dict) for item in raw_steps):
        raise ValueError('Cada etapa debe ser un objeto')
    preset = VisualWorkflowPreset(kind=kind, steps=tuple(VisualWorkflowStep.from_mapping(item) for item in raw_steps))
    return validate_assignments(preset, load_agent_profiles(project_root)) if validate_agents else validate_preset(preset)


def workflow_catalog_revision(project_root: Path) -> str:
    from factoria.application.project_integration import project_path
    digest = hashlib.sha256()
    # A draft's agent references must refer to the catalog version it displayed.
    digest.update(agent_catalog_revision(project_root).encode())
    for relative in (_PRESET_FILE, _LEGACY_PRESET_FILE):
        path = project_path(project_root, relative.as_posix())
        digest.update(relative.as_posix().encode())
        digest.update(b'\x01' + path.read_bytes() if path.exists() else b'\x00')
    return digest.hexdigest()


def workflow_catalog_snapshot(project_root: Path) -> tuple[dict[str, VisualWorkflowPreset], str]:
    with _WORKFLOW_LOCK:
        revision = workflow_catalog_revision(project_root)
        presets = {kind: load_preset(project_root, kind) for kind in ('feature', 'fix')}
        if revision != workflow_catalog_revision(project_root):
            raise WorkflowCatalogConflict('Los flujos cambiaron durante la lectura; recarga el catálogo')
        return presets, revision


def save_preset(project_root: Path, preset: VisualWorkflowPreset, *, expected_revision: str | None = None) -> Path:
    with _WORKFLOW_LOCK:
        return _save_preset(project_root, preset, expected_revision=expected_revision)


def _save_preset(project_root: Path, preset: VisualWorkflowPreset, *, expected_revision: str | None) -> Path:
    from factoria.application.governance import ExecutionGovernor, GovernedAction
    from factoria.application.policy_runtime import build_execution_context
    from factoria.application.project_integration import project_path
    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(project_root))
    path = project_path(project_root, _PRESET_FILE.as_posix())
    revision = workflow_catalog_revision(project_root)
    if expected_revision is not None and revision != expected_revision:
        raise WorkflowCatalogConflict('Los flujos cambiaron fuera de este editor; recarga antes de guardar')
    checked = validate_assignments(preset, load_agent_profiles(project_root))
    payload = {kind: load_preset(project_root, kind).to_mapping() for kind in ('feature', 'fix')}
    payload[checked.kind] = checked.to_mapping()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if revision != workflow_catalog_revision(project_root):
            raise WorkflowCatalogConflict('Los flujos cambiaron durante el guardado; vuelve a cargar')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def preset_to_workflow(preset: VisualWorkflowPreset, *, project_root: Path | None = None) -> AgentWorkflow:
    profiles = load_agent_profiles(project_root)
    checked = validate_assignments(preset, profiles)
    agent_defaults = {
        item.role: item
        for item in profiles
    }
    steps: list[AgentStep] = []
    for item in checked.steps:
        if not item.enabled:
            continue
        default = agent_defaults[item.agent_id or item.role]
        steps.append(
            AgentStep(
                name=item.name,
                role=_ROLE_BY_NAME[item.name],
                profile=ModelProfile(item.profile or default.profile),
                preferred_tool=item.tool or default.platform,
                agent_id=item.agent_id,
            )
        )
    return AgentWorkflow(kind=checked.kind, steps=tuple(steps))


def workflow_snapshot(workflow: AgentWorkflow) -> tuple[dict[str, str | None], ...]:
    return tuple(
        {
            'name': step.name,
            'role': step.role.value,
            'profile': step.profile.value if step.profile else None,
            'preferred_tool': step.preferred_tool,
            **({'agent_id': step.agent_id} if step.agent_id is not None else {}),
        }
        for step in workflow.steps
    )


def workflow_from_snapshot(kind: str, raw_steps: tuple[dict[str, Any], ...]) -> AgentWorkflow:
    steps: list[AgentStep] = []
    for raw in raw_steps:
        name = str(raw.get('name', ''))
        role = AgentRole(str(raw.get('role', '')))
        profile_raw = raw.get('profile')
        preferred_tool = raw.get('preferred_tool')
        agent_id = raw.get('agent_id')
        if agent_id is not None and (not isinstance(agent_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', agent_id)):
            raise ValueError('Identificador de agente no válido en la snapshot')
        steps.append(
            AgentStep(
                name=name,
                role=role,
                profile=ModelProfile(str(profile_raw)) if profile_raw else None,
                preferred_tool=str(preferred_tool) if preferred_tool else None,
                agent_id=agent_id,
            )
        )
    return AgentWorkflow(kind=kind, steps=tuple(steps))
