from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from factoria.orchestration.models import AgentRole, ModelProfile, ROLE_SPECS

_AGENT_FILE = Path('.factoria') / 'ui-agents.json'
_ALLOWED_PLATFORMS = {None, '', 'codex', 'opencode'}


@dataclass(frozen=True, slots=True)
class AgentRoleProfile:
    role: str
    profile: str
    platform: str | None = None
    timeout_seconds: int = 1800

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> 'AgentRoleProfile':
        return cls(
            role=str(data.get('role', '')),
            profile=str(data.get('profile', '')),
            platform=str(data['platform']) if data.get('platform') else None,
            timeout_seconds=int(data.get('timeout_seconds', 1800)),
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def default_agent_profiles() -> tuple[AgentRoleProfile, ...]:
    return tuple(
        AgentRoleProfile(
            role=role.value,
            profile=spec.default_profile.value,
            platform=None,
            timeout_seconds=1800,
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
    if profile.timeout_seconds < 30 or profile.timeout_seconds > 7200:
        raise ValueError('El timeout del agente debe estar entre 30 y 7200 segundos')
    return AgentRoleProfile(
        role=role.value,
        profile=model_profile.value,
        platform=profile.platform or None,
        timeout_seconds=profile.timeout_seconds,
    )


def load_agent_profiles(project_root: Path | None) -> tuple[AgentRoleProfile, ...]:
    defaults = {item.role: item for item in default_agent_profiles()}
    if project_root is None:
        return tuple(defaults.values())
    path = project_root / _AGENT_FILE
    if not path.exists():
        return tuple(defaults.values())
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return tuple(defaults.values())
    if not isinstance(raw, dict):
        return tuple(defaults.values())
    for role, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            item = validate_agent_profile(AgentRoleProfile.from_mapping({'role': role, **value}))
        except (ValueError, TypeError):
            continue
        defaults[item.role] = item
    return tuple(defaults[role.value] for role in AgentRole)


def save_agent_profile(project_root: Path, profile: AgentRoleProfile) -> Path:
    checked = validate_agent_profile(profile)
    path = project_root / _AGENT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(existing, dict):
                payload = existing
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload[checked.role] = {
        'profile': checked.profile,
        'platform': checked.platform,
        'timeout_seconds': checked.timeout_seconds,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def profile_for(project_root: Path | None, role: AgentRole) -> AgentRoleProfile:
    return next(item for item in load_agent_profiles(project_root) if item.role == role.value)
