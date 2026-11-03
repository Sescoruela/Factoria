from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factoria.application.agent_profiles import load_agent_profiles
from factoria.orchestration import AgentRole, AgentStep, AgentWorkflow, AgentWorkflowPlanner, ModelProfile

_PRESET_FILE = Path('.factoria') / 'ui-workflows.json'
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


@dataclass(frozen=True, slots=True)
class VisualWorkflowStep:
    name: str
    role: str
    profile: str | None = None
    tool: str | None = None
    enabled: bool = True

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> 'VisualWorkflowStep':
        return cls(
            name=str(data.get('name', '')),
            role=str(data.get('role', '')),
            profile=str(data['profile']) if data.get('profile') else None,
            tool=str(data['tool']) if data.get('tool') else None,
            enabled=bool(data.get('enabled', True)),
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
                    profile=step.profile.value if step.profile else None,
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


def load_preset(project_root: Path, kind: str, *, large_fix: bool = False, update_memory: bool = False) -> VisualWorkflowPreset:
    fallback = default_preset(kind, large_fix=large_fix, update_memory=update_memory)
    path = project_root / _PRESET_FILE
    if not path.exists():
        return fallback
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(raw, dict):
        return fallback
    entry = raw.get(kind)
    if not isinstance(entry, dict):
        return fallback
    raw_steps = entry.get('steps')
    if not isinstance(raw_steps, list):
        return fallback
    try:
        preset = VisualWorkflowPreset(
            kind=kind,
            steps=tuple(
                VisualWorkflowStep.from_mapping(item)
                for item in raw_steps
                if isinstance(item, dict)
            ),
        )
        return validate_preset(preset)
    except ValueError:
        return fallback


def save_preset(project_root: Path, preset: VisualWorkflowPreset) -> Path:
    checked = validate_preset(preset)
    path = project_root / _PRESET_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(existing, dict):
                payload = existing
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload[checked.kind] = checked.to_mapping()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def preset_to_workflow(preset: VisualWorkflowPreset, *, project_root: Path | None = None) -> AgentWorkflow:
    checked = validate_preset(preset)
    agent_defaults = {
        item.role: item
        for item in load_agent_profiles(project_root)
    }
    steps: list[AgentStep] = []
    for item in checked.steps:
        if not item.enabled:
            continue
        default = agent_defaults[item.role]
        steps.append(
            AgentStep(
                name=item.name,
                role=_ROLE_BY_NAME[item.name],
                profile=ModelProfile(item.profile or default.profile),
                preferred_tool=item.tool or default.platform,
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
        steps.append(
            AgentStep(
                name=name,
                role=role,
                profile=ModelProfile(str(profile_raw)) if profile_raw else None,
                preferred_tool=str(preferred_tool) if preferred_tool else None,
            )
        )
    return AgentWorkflow(kind=kind, steps=tuple(steps))
