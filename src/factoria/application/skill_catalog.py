"""Project-owned Markdown skills, edited without executing a coding tool."""
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

_DIRECTORY = '.factoria/skills'
_MARKER = '<!-- factoria:skill:v1 -->'
_LOCK = threading.RLock()


class SkillCatalogConflict(ValueError):
    """The catalog changed since the editor loaded its draft."""


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    id: str
    name: str
    description: str = ''
    content: str = ''

    @property
    def path(self) -> str:
        return f'{_DIRECTORY}/{self.id}.md'

    def to_mapping(self) -> dict[str, str]:
        return {**asdict(self), 'path': self.path}

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> SkillDefinition:
        fields = {key: data.get(key, '') for key in ('id', 'name', 'description', 'content')}
        if not all(isinstance(value, str) for value in fields.values()):
            raise ValueError('Identificador, nombre, descripción y contenido deben ser texto')
        return cls(**fields)


def validate_skill(skill: SkillDefinition) -> SkillDefinition:
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', skill.id):
        raise ValueError('Identificador no válido: hasta 64 letras minúsculas, números y guiones')
    if skill.id in {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}:
        raise ValueError('El identificador está reservado en Windows; elige otro')
    if not skill.name.strip() or len(skill.name) > 120:
        raise ValueError('Escribe un nombre de hasta 120 caracteres')
    if len(skill.description) > 1000 or len(skill.content) > 100000:
        raise ValueError('La descripción admite 1000 caracteres y el contenido 100000')
    if not skill.content.strip():
        raise ValueError('La skill necesita contenido Markdown')
    return skill


def _files(root: Path) -> tuple[Path, ...]:
    from factoria.application.project_integration import project_path
    directory = project_path(root, _DIRECTORY)
    if not directory.exists():
        return ()
    if not directory.is_dir():
        raise ValueError('El catálogo de skills debe ser una carpeta')
    return tuple(project_path(root, p.relative_to(root).as_posix()) for p in sorted(directory.iterdir())
                 if p.suffix.lower() == '.md')


def skill_catalog_revision(root: Path | None) -> str:
    digest = hashlib.sha256()
    if root is not None:
        root = root.resolve()
        from factoria.application.resource_archive import archive_revision
        digest.update(archive_revision(root).encode())
        for path in _files(root):
            digest.update(path.name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def _decode(path: Path) -> SkillDefinition | None:
    text = path.read_bytes().decode('utf-8')
    return decode_skill_text(text, path.name)


def decode_skill_text(text: str, filename: str) -> SkillDefinition | None:
    """Decode a captured skill without reopening a possibly changing file."""
    if not text.startswith(_MARKER):
        return None  # Foreign files are never claimed or overwritten.
    parts = text.split('\n', 6)
    try:
        if len(parts) != 7 or parts[0] != _MARKER or parts[1] != '---' or parts[5] != '---':
            raise ValueError('Cabecera incompleta')
        if any(not parts[index].startswith(key + ': ') for index, key in enumerate(('id', 'name', 'description'), 2)):
            raise ValueError('Metadatos no válidos')
        data = {key: json.loads(parts[index].removeprefix(key + ': '))
                for index, key in enumerate(('id', 'name', 'description'), 2)}
        skill = validate_skill(SkillDefinition.from_mapping({**data, 'content': parts[6]}))
        if filename != skill.id + '.md':
            raise ValueError('El identificador no coincide con el archivo')
        return skill
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Skill no válida: {filename}: {exc}') from exc


def skill_catalog_snapshot(root: Path | None) -> tuple[tuple[SkillDefinition, ...], str, tuple[str, ...]]:
    with _LOCK:
        revision = skill_catalog_revision(root)
        skills, foreign = [], []
        if root is not None:
            for path in _files(root.resolve()):
                from factoria.application.resource_archive import assert_not_archived
                assert_not_archived(root, 'skill', path.stem)
                item = _decode(path)
                if item is None:
                    foreign.append(path.name)
                else:
                    skills.append(item)
        if revision != skill_catalog_revision(root):
            raise SkillCatalogConflict('El catálogo cambió durante la lectura; vuelve a cargarlo')
        return tuple(skills), revision, tuple(foreign)


def save_skill(root: Path, skill: SkillDefinition, *, expected_revision: str, create: bool = False) -> Path:
    from factoria.application.governance import ExecutionGovernor, GovernedAction
    from factoria.application.policy_runtime import build_execution_context
    from factoria.application.project_integration import project_path
    from factoria.security import SecretScanner
    root = root.resolve()
    ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(root))
    checked = validate_skill(skill)
    from factoria.application.resource_archive import assert_not_archived
    assert_not_archived(root, 'skill', checked.id)
    if any(SecretScanner().scan_text(value, location=skill.id)
           for value in (skill.name, skill.description, skill.content)):
        raise ValueError('Posible secreto en la skill; no se guarda')
    with _LOCK:
        assert_not_archived(root, 'skill', checked.id)
        revision = skill_catalog_revision(root)
        if revision != expected_revision:
            raise SkillCatalogConflict('Las skills cambiaron fuera de este editor; recarga antes de guardar')
        # Validate the catalog before changing any source.
        skill_catalog_snapshot(root)
        target = project_path(root, checked.path)
        aliases = [p for p in _files(root) if p.name.casefold() == target.name.casefold()]
        if create and aliases:
            raise ValueError('Ya existe un archivo o skill con ese identificador')
        if not create:
            if not target.is_file():
                raise ValueError('La skill que quieres modificar no existe')
            if _decode(target) is None:
                raise ValueError('El archivo es ajeno al catálogo; no se sobrescribe')
        header = '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}'
                           for key, value in (('id', skill.id), ('name', skill.name), ('description', skill.description)))
        text = _MARKER + '\n---\n' + header + '\n---\n' + skill.content
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(text.encode('utf-8'))
                handle.flush()
                os.fsync(handle.fileno())
            if revision != skill_catalog_revision(root):
                raise SkillCatalogConflict('Las skills cambiaron durante el guardado; vuelve a cargar')
            if create:
                # Exclusive creation also protects against a foreign file appearing at the last moment.
                try:
                    os.link(temporary, target)
                except FileExistsError as exc:
                    raise SkillCatalogConflict('El archivo ya existe; vuelve a cargar el catálogo') from exc
            else:
                os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return target
