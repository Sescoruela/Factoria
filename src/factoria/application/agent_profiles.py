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

from factoria.orchestration.models import AgentRole, ModelProfile, ROLE_SPECS

_AGENT_FILE = Path('.factoria') / 'agents.json'
_LEGACY_AGENT_FILE = Path('.factoria') / 'ui-agents.json'
_ALLOWED_PLATFORMS = {None, '', 'codex', 'opencode'}
_CATALOG_LOCK = threading.RLock()


class AgentCatalogConflict(ValueError):
    """The editor's saved version no longer matches the project catalog."""


@dataclass(frozen=True, slots=True)
class AgentRoleProfile:
    role: str
    profile: str
    platform: str | None = None
    instructions: str = ''
    skills: tuple[str, ...] = ()
    base_role: str | None = None
    name: str = ''
    description: str = ''

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> 'AgentRoleProfile':
        instructions = data.get('instructions', '')
        skills = data.get('skills', [])
        for field in ('role', 'profile', 'name', 'description'):
            if field in data and not isinstance(data[field], str):
                raise ValueError(f'{field} debe ser texto')
        for field in ('base_role', 'platform'):
            if data.get(field) is not None and not isinstance(data[field], str):
                raise ValueError(f'{field} debe ser texto')
        if not isinstance(instructions, str) or not isinstance(skills, (list, tuple)) or not all(isinstance(s, str) for s in skills):
            raise ValueError('Las instrucciones deben ser texto y las skills una lista de rutas')
        return cls(
            role=str(data.get('role', '')),
            profile=str(data.get('profile', '')),
            platform=str(data['platform']) if data.get('platform') else None,
            instructions=instructions,
            skills=tuple(skills),
            base_role=data.get('base_role'),
            name=data.get('name', ''),
            description=data.get('description', ''),
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
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', profile.role):
        raise ValueError('Identificador no válido: usa hasta 64 letras minúsculas, números y guiones')
    try:
        role = AgentRole(profile.base_role or profile.role)
    except ValueError as exc:
        raise ValueError(f'Agente no válido: {profile.role}') from exc
    if profile.role in {item.value for item in AgentRole} and role.value != profile.role:
        raise ValueError('El rol base de un agente básico no puede cambiar')
    if not isinstance(profile.name, str) or not isinstance(profile.description, str) or len(profile.name) > 120 or len(profile.description) > 1000:
        raise ValueError('Nombre o descripción no válidos (máximo 120 y 1000 caracteres)')
    if profile.role not in {item.value for item in AgentRole} and not profile.name.strip():
        raise ValueError('El agente personalizado necesita un nombre')
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
        role=profile.role,
        profile=model_profile.value,
        platform=profile.platform or None,
        instructions=profile.instructions,
        skills=tuple(dict.fromkeys(profile.skills)),
        base_role=role.value if profile.role != role.value else None,
        name=profile.name.strip(),
        description=profile.description,
    )


def load_agent_profiles(project_root: Path | None) -> tuple[AgentRoleProfile, ...]:
    defaults = {item.role: item for item in default_agent_profiles()}
    if project_root is None:
        return tuple(defaults.values())
    from factoria.application.project_integration import project_path
    path = project_path(project_root, _AGENT_FILE.as_posix())
    if not path.exists():
        path = project_path(project_root, _LEGACY_AGENT_FILE.as_posix())
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
    return tuple(defaults.values())


def agent_catalog_revision(project_root: Path | None) -> str:
    """Hash source bytes, including legacy data, to detect external editor changes."""
    from factoria.application.project_integration import project_path
    digest = hashlib.sha256()
    if project_root is not None:
        for relative in (_AGENT_FILE, _LEGACY_AGENT_FILE):
            path = project_path(project_root, relative.as_posix())
            digest.update(relative.as_posix().encode())
            digest.update(b'\x01' + path.read_bytes() if path.exists() else b'\x00')
    return digest.hexdigest()


def agent_catalog_snapshot(project_root: Path | None) -> tuple[tuple[AgentRoleProfile, ...], str]:
    with _CATALOG_LOCK:
        before = agent_catalog_revision(project_root)
        profiles = load_agent_profiles(project_root)
        if before != agent_catalog_revision(project_root):
            raise AgentCatalogConflict('El catálogo cambió durante la lectura; vuelve a cargarlo')
        return profiles, before


def save_agent_profile(project_root: Path, profile: AgentRoleProfile, *, expected_revision: str | None = None, mode: str = 'upsert') -> Path:
    with _CATALOG_LOCK:
        return _save_agent_profile(project_root, profile, expected_revision=expected_revision, mode=mode)


def _save_agent_profile(project_root: Path, profile: AgentRoleProfile, *, expected_revision: str | None, mode: str) -> Path:
    from factoria.application.governance import ExecutionGovernor, GovernedAction
    from factoria.application.policy_runtime import build_execution_context
    from factoria.application.project_integration import project_path
    from factoria.security import SecretScanner
    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(project_root))
    checked = validate_agent_profile(profile)
    if SecretScanner().scan_text('\n'.join((checked.name, checked.description, checked.instructions)), location=checked.role):
        raise ValueError('Posible secreto en las instrucciones; no se guarda')
    path = project_path(project_root, _AGENT_FILE.as_posix())
    revision = agent_catalog_revision(project_root)
    if expected_revision is not None and expected_revision != revision:
        raise AgentCatalogConflict('El catálogo cambió fuera de este editor; recarga antes de guardar')
    payload = {item.role: item.to_mapping() for item in load_agent_profiles(project_root)}
    if mode not in {'create', 'update', 'upsert'}:
        raise ValueError('Operación de agente no válida')
    if mode == 'create' and checked.role in payload:
        raise ValueError('Ya existe un agente con ese identificador')
    if mode == 'update' and checked.role not in payload:
        raise ValueError('El agente que quieres modificar no existe')
    for skill in checked.skills:
        if not project_path(project_root, skill).is_file():
            raise ValueError(f'La skill no existe en el proyecto: {skill}')
    payload[checked.role] = checked.to_mapping()
    # Changing a referenced agent's base role must not invalidate an existing flow.
    from factoria.application.workflow_presets import load_preset, validate_assignments, workflow_catalog_revision
    workflow_revision = workflow_catalog_revision(project_root)
    profiles = tuple(AgentRoleProfile.from_mapping(value) for value in payload.values())
    for kind in ('fix', 'feature'):
        validate_assignments(load_preset(project_root, kind, validate_agents=False), profiles)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if agent_catalog_revision(project_root) != revision or workflow_catalog_revision(project_root) != workflow_revision:
            raise AgentCatalogConflict('El catálogo cambió durante el guardado; vuelve a cargarlo')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def profile_for(project_root: Path | None, role: AgentRole) -> AgentRoleProfile:
    return next(item for item in load_agent_profiles(project_root) if item.role == role.value)
