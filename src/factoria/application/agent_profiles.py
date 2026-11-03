from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factoria.orchestration.models import AgentRole, ModelProfile, ROLE_SPECS

_AGENT_FILE = Path('.factoria') / 'agents.json'
_LEGACY_AGENT_FILE = Path('.factoria') / 'ui-agents.json'
_ALLOWED_PLATFORMS = {None, '', 'codex', 'opencode'}


@dataclass(frozen=True, slots=True)
class AgentRoleProfile:
    role: str
    profile: str
    platform: str | None = None
    instructions: str = ''
    skills: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> 'AgentRoleProfile':
        instructions = data.get('instructions', '')
        skills = data.get('skills', [])
        if not isinstance(instructions, str) or not isinstance(skills, (list, tuple)) or not all(isinstance(s, str) for s in skills):
            raise ValueError('Las instrucciones deben ser texto y las skills una lista de rutas')
        return cls(
            role=str(data.get('role', '')),
            profile=str(data.get('profile', '')),
            platform=str(data['platform']) if data.get('platform') else None,
            instructions=instructions,
            skills=tuple(skills),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def default_agent_profiles() -> tuple[AgentRoleProfile, ...]:
    return tuple(
        AgentRoleProfile(
            role=role.value,
            profile=spec.default_profile.value,
            platform=None,
        )
        for role, spec in ROLE_SPECS.items()
    )


def validate_agent_profile(profile: AgentRoleProfile) -> AgentRoleProfile:
    try:
        role = AgentRole(profile.role)
    except ValueError as exc:
        raise ValueError(f'Agente no válido: {profile.role}') from exc
    try:
        model_profile = ModelProfile(profile.profile)
    except ValueError as exc:
        raise ValueError(f'Perfil no válido para {profile.role}: {profile.profile}') from exc
    if profile.platform not in _ALLOWED_PLATFORMS:
        raise ValueError(f'Plataforma no válida para {profile.role}: {profile.platform}')
    from pathlib import PurePosixPath, PureWindowsPath
    for skill in profile.skills:
        if not skill or '\\' in skill or PurePosixPath(skill).is_absolute() or PureWindowsPath(skill).drive or '..' in PurePosixPath(skill).parts or not skill.endswith('.md'):
            raise ValueError('Las skills deben ser rutas Markdown relativas dentro del proyecto')
    if len(profile.instructions) > 20000:
        raise ValueError('Las instrucciones del agente superan 20000 caracteres')
    return AgentRoleProfile(
        role=role.value,
        profile=model_profile.value,
        platform=profile.platform or None,
        instructions=profile.instructions,
        skills=tuple(dict.fromkeys(profile.skills)),
    )


def load_agent_profiles(project_root: Path | None) -> tuple[AgentRoleProfile, ...]:
    defaults = {item.role: item for item in default_agent_profiles()}
    if project_root is None:
        return tuple(defaults.values())
    path = project_root / _AGENT_FILE
    if not path.exists():
        path = project_root / _LEGACY_AGENT_FILE
    if not path.exists():
        return tuple(defaults.values())
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('La configuración de agentes no es válida') from exc
    if not isinstance(raw, dict):
        raise ValueError('La configuración de agentes debe ser un objeto')
    for role, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(f'Configuración no válida para {role}')
        item = validate_agent_profile(AgentRoleProfile.from_mapping({**value, 'role': role}))
        defaults[item.role] = item
    return tuple(defaults[role.value] for role in AgentRole)


def save_agent_profile(project_root: Path, profile: AgentRoleProfile) -> Path:
    from factoria.application.governance import ExecutionGovernor, GovernedAction
    from factoria.application.policy_runtime import build_execution_context
    from factoria.application.project_integration import project_path
    from factoria.security import SecretScanner
    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(project_root))
    checked = validate_agent_profile(profile)
    if SecretScanner().scan_text(checked.instructions, location=checked.role):
        raise ValueError('Posible secreto en las instrucciones; no se guarda')
    path = project_path(project_root, _AGENT_FILE.as_posix())
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {item.role: item.to_mapping() for item in load_agent_profiles(project_root)}
    payload[checked.role] = checked.to_mapping()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def profile_for(project_root: Path | None, role: AgentRole) -> AgentRoleProfile:
    return next(item for item in load_agent_profiles(project_root) if item.role == role.value)
