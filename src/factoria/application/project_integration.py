"""Compile shared project settings into repo-local, tool-discoverable assets.

No provider call, global configuration change or permission escalation occurs here.
Generated files are owned by a hash manifest; user edits cause a conflict.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from factoria.application.agent_profiles import load_agent_profiles
from factoria.application.governance import ExecutionGovernor, GovernedAction
from factoria.application.policy_runtime import build_execution_context
from factoria.application.workflow_presets import load_preset, preset_to_workflow, workflow_snapshot
from factoria.config.loader import load_project_config
from factoria.security import SecretScanner

START = '<!-- factoria:integration:start -->'
END = '<!-- factoria:integration:end -->'
MANIFEST = '.factoria/integration-manifest.json'


def project_path(root: Path, relative: str) -> Path:
    """Reject traversal, symlink targets and Windows drive paths on every OS."""
    from pathlib import PurePosixPath, PureWindowsPath
    if not relative or '\\' in relative or PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).drive or '..' in PurePosixPath(relative).parts:
        raise ValueError('La ruta debe ser relativa al proyecto')
    root = root.resolve()
    target = root / relative
    for item in (target, *target.parents):
        if item == root:
            break
        if item.is_symlink():
            raise ValueError('La integración no sigue enlaces simbólicos')
    if not target.resolve().is_relative_to(root):
        raise ValueError('Ruta fuera del proyecto')
    return target


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _read(path: Path) -> str:
    # Disable newline translation so handwritten AGENTS content stays byte-identical.
    with path.open(encoding='utf-8', newline='') as handle:
        return handle.read()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def project_definition(root: Path) -> dict:
    from factoria.application.skill_catalog import skill_catalog_snapshot
    project_path(root, '.factoria/config.toml')
    roles = []
    for item in load_agent_profiles(root):
        data = item.to_mapping()
        data['skill_contents'] = {
            name: _read(project_path(root, name)) for name in item.skills
        }
        if any(SecretScanner().scan_text(text, location=item.role) for text in (item.instructions, *data['skill_contents'].values())):
            raise ValueError('Posible secreto en instrucciones o skills; exportación bloqueada')
        roles.append(data)
    config = load_project_config(root / '.factoria/config.toml')
    flows = {
        kind: list(workflow_snapshot(preset_to_workflow(load_preset(root, kind), project_root=root)))
        for kind in ('fix', 'feature')
        if kind not in config.blocked_flows and (not config.allowed_flows or kind in config.allowed_flows)
    }
    skills, _revision, _foreign = skill_catalog_snapshot(root)
    definition = {'schema_version': 1, 'agents': roles, 'workflows': flows,
                  'skills': [skill.to_mapping() for skill in skills]}
    if SecretScanner().scan_text(_json(definition), location='project-definition'):
        raise ValueError('Se ha detectado un posible secreto en la configuración; no se exporta')
    return definition


def workflow_guide(kind: str, definition: dict) -> str:
    rows = []
    agents = {a['role']: a for a in definition['agents']}
    for index, step in enumerate(definition['workflows'][kind], 1):
        role = agents[step.get('agent_id') or step['role']]
        rows.append(f"{index}. **{step['name']} / {step['role']}** · agente `{role['role']}` · perfil `{step['profile']}` · plataforma `{step['preferred_tool'] or 'sesión actual'}`")
        if role['instructions']:
            rows.append('\n' + role['instructions'] + '\n')
        for name in role['skills']:
            rows.append(f"   - Consultar `{name}` antes de realizar esta etapa.")
    return f'''# Flujo {kind}

Ejecutar este flujo dentro de la sesión actual de Codex u OpenCode.
La configuración vigente está en `.factoria/agents.json`, `.factoria/workflows.json`
y `.factoria/config.toml`. Antes de empezar ejecutar `factoria project check`.
Si la integración está desactualizada, pedir regenerarla; no usar instrucciones antiguas.

## Inicio y seguimiento

1. Leer `AGENTS.md` y solo la memoria relevante de `docs/memoria/`.
2. Ejecutar `factoria native start {kind} --tool <codex|opencode> --task "<petición>"`.
   Requiere una rama de trabajo y árbol limpio. Pedir crear/cambiar rama si procede.
   Este comando prepara el seguimiento local; NO inicia otro LLM.
3. Leer la salida JSON y su campo `instruction`; realizar únicamente la etapa indicada.
4. Guardar la evidencia en el archivo indicado por `evidence_file` y ejecutar
   `factoria native next <flow-id>`. Repetir hasta `ready_for_commit`.
5. Para los puntos de aprobación, mostrar el plan o resultado y ESPERAR respuesta humana.
   Solo tras recibirla, usar `--approve-plan`, `--approve-final` o `--confirm-manual`.
   Si hay consumidores externos afectados, revisar el impacto y confirmar por separado
   con `--confirm-external-impact`. No afirmar que esos servicios fueron comprobados
   sin evidencia de acceso y verificación.
   Nunca interpretar la petición inicial como aprobación de estos puntos posteriores.
6. Preparar un resumen y mensaje de commit; commit, push y PR requieren la autorización
   correspondiente. Tras el commit y árbol limpio: `factoria native finish <flow-id>`.
   Pausa/reanudación: `factoria native pause|resume <flow-id>`.
   Cancelar sin borrar código ni ramas: `factoria native cancel <flow-id> --yes`.

## Etapas configuradas

{chr(10).join(rows)}

La verificación se inserta obligatoriamente antes de review. Factoria ejecuta solo
comandos confirmados en la memoria; si no existen, requiere comprobación manual humana.
Para review, escribir JSON con result (approved o changes_required),
acceptance_criteria_met (boolean), mandatory_rules_violated (lista), findings
(lista de severity critical/important/minor y message), risks (lista) y recommendation.
Si hay hallazgos bloqueantes, no avanzar: corregir y volver a verificar con
`factoria native retry <flow-id>`; no alterar la evidencia para ocultarlos.

## Límites

Si una etapa pide otra plataforma, detenerse y abrir esa herramienta para continuar
el mismo flujo. No simular un cambio de plataforma o modelo. El perfil es una
preferencia: en uso directo el usuario selecciona el modelo en la herramienta.
Respetar sus permisos y sandbox; estas instrucciones no los sustituyen ni los amplían.
Si no está disponible Factoria o el repositorio, informar del bloqueo, no afirmar
que se han ejecutado las etapas o comprobaciones. No lanzar `factoria fix/feature`
desde esta skill: esos comandos pertenecen al modo orquestado y llamarían a otro LLM.
'''


@dataclass(frozen=True)
class IntegrationPlan:
    files: dict[str, str]
    changed: tuple[str, ...]
    conflicts: tuple[str, ...]


class ProjectIntegration:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def plan(self) -> IntegrationPlan:
        definition = project_definition(self.root)
        files = {'.factoria/agents.json': _json({a['role']: {k: v for k, v in a.items() if k != 'skill_contents'} for a in definition['agents']}),
                 '.factoria/workflows.json': _json({kind: load_preset(self.root, kind).to_mapping() for kind in ('fix', 'feature')})}
        # Source files are user-maintained; include them for migration, never own them.
        source_files = set(files)
        catalog = '# Agentes del proyecto\n\n'
        catalog += 'Catálogo compartido por Codex y OpenCode. Las etapas pueden seleccionar agentes compatibles por identificador, conservando el rol y los controles del flujo.\n\n'
        for agent in definition['agents']:
            catalog += f"## {agent['name'] or agent['role']} ({agent['role']})\n\n"
            catalog += f"Rol base: {agent['base_role'] or agent['role']} · perfil: {agent['profile']} · plataforma preferida: {agent['platform'] or 'sesión actual'}\n\n"
            catalog += agent['description'] + '\n\n' + agent['instructions'] + '\n\n'
            catalog += '\n'.join(f'Consultar `{skill}`.' for skill in agent['skills']) + '\n\n'
        files['.factoria/generated/agents.md'] = catalog
        skills_guide = '# Skills del proyecto\n\nConsultar las skills asignadas al agente antes de realizar su etapa.\n\n'
        for skill in definition['skills']:
            skills_guide += f"## {skill['name']} ({skill['id']})\n\nFuente: `{skill['path']}`\n\n{skill['description']}\n\n{skill['content']}\n\n"
        files['.factoria/generated/skills.md'] = skills_guide
        for kind in definition['workflows']:
            guide = workflow_guide(kind, definition)
            files[f'.factoria/generated/{kind}.md'] = guide
            files[f'.agents/skills/factoria-{kind}/SKILL.md'] = (
                f'---\nname: factoria-{kind}\ndescription: '
                + ('"Corregir errores, bugs, fallos o regresiones siguiendo el flujo fix de este proyecto. No usar para funcionalidades nuevas."' if kind == 'fix' else '"Implementar funcionalidades nuevas siguiendo el flujo feature de este proyecto. No usar para correcciones pequeñas."')
                + '\n---\n\n' + guide)
            files[f'.opencode/commands/factoria-{kind}.md'] = (
                f'---\ndescription: Ejecutar el flujo {kind} configurado en Factoria\n---\n\n'
                f'Petición del usuario: $ARGUMENTS\n\n' + guide)
        for role in definition['agents']:
            permission = {'*': 'deny', 'read': 'allow', 'glob': 'allow', 'grep': 'allow', 'list': 'allow', 'skill': 'allow'}
            if (role.get('base_role') or role['role']) == 'implementer':
                permission['edit'] = 'ask'
            files[f".opencode/agents/factoria-{role['role']}.md"] = (
                '---\ndescription: ' + role['role'] + ' del proyecto Factoría\nmode: subagent\npermission: '
                + json.dumps(permission) + '\n---\n\n'
                + role['instructions'] + '\n\nLeer AGENTS.md y seguir el flujo activo. No omitir sus controles.\n'
                + '\n'.join(f'Consultar `{path}`.' for path in role['skills']) + '\n')
        block = START + '''
## Factoría: agentes y flujos del proyecto
Consultar el catálogo de agentes en `.factoria/generated/agents.md`.
Consultar el catálogo de skills en `.factoria/generated/skills.md` y los archivos asignados a cada agente.
Cada etapa usa el agente configurado en su campo agent_id; si está vacío, usa el agente básico del rol. Mantener sus controles obligatorios.
Antes de cambiar código, seleccionar el flujo configurado según la intención:
- Corrección, bug, fallo o regresión → skill `factoria-fix`.
- Funcionalidad o capacidad nueva → skill `factoria-feature`.
- Petición ambigua o mezcla de trabajos → aclarar el alcance antes de iniciar.
Leer `.factoria/generated/<flujo>.md` y ejecutar `factoria project check`.
No inventar ni sustituir el flujo por uno genérico. Si el flujo está deshabilitado,
la herramienta carece de acceso o falta el runtime, informar del bloqueo.
Codex y OpenCode pueden usar estas instrucciones con Factoría cerrada.
Los permisos y aprobaciones de la herramienta siguen vigentes.
''' + END
        agents_path = project_path(self.root, 'AGENTS.md')
        original = _read(agents_path) if agents_path.exists() else ''
        if original.count(START) != original.count(END) or original.count(START) > 1:
            raise ValueError('Bloque de integración AGENTS.md ambiguo')
        if START in original and original.index(START) > original.index(END):
            raise ValueError('Bloque de integración AGENTS.md invertido')
        if START in original:
            before, rest = original.split(START, 1)
            _, after = rest.split(END, 1)
            files['AGENTS.md'] = before + block + after
        else:
            files['AGENTS.md'] = original + ('\n\n' if original else '') + block + '\n'
        bundle = '# Contexto portable de Factoría\n\n'
        bundle += 'Para ChatGPT sin acceso al repositorio: adjuntar este documento y los archivos de código necesarios.\n'
        bundle += 'Sin herramientas no hay ejecución, verificación ni seguimiento automático; presentar propuestas y pasos pendientes.\n\n'
        bundle += '## Configuración\n\n```json\n' + _json(definition) + '```\n\n'
        bundle += '\n\n'.join(workflow_guide(k, definition) for k in definition['workflows'])
        for relative in ('AGENTS.md', 'docs/memoria/arquitectura.md', 'docs/memoria/flujos.md', 'docs/memoria/decisiones.md', 'docs/memoria/testing.md'):
            path = project_path(self.root, relative)
            if path.is_file() or relative == 'AGENTS.md':
                bundle += f'\n\n## Archivo {relative}\n\n' + (files['AGENTS.md'] if relative == 'AGENTS.md' else _read(path))
        files['.factoria/generated/chatgpt-context.md'] = bundle
        manifest_path = project_path(self.root, MANIFEST)
        old = json.loads(_read(manifest_path)) if manifest_path.exists() else {}
        owned = old.get('files', {})
        conflicts, changed = [], []
        for name, content in files.items():
            path = project_path(self.root, name)
            current = _read(path) if path.exists() else None
            if current == content:
                continue
            changed.append(name)
            if name in source_files or name == 'AGENTS.md':
                continue
            if current is not None and _digest(current) != owned.get(name):
                conflicts.append(name)
        # Do not leave discoverable skills/commands behind when a flow is disabled.
        for name, checksum in owned.items():
            if name in files:
                continue
            if not (name.startswith('.factoria/generated/') or name.startswith('.agents/skills/factoria-') or name.startswith('.opencode/commands/factoria-') or name.startswith('.opencode/agents/factoria-')):
                raise ValueError('Ruta no gestionada en el manifiesto')
            path = project_path(self.root, name)
            if path.exists() and _digest(_read(path)) != checksum:
                conflicts.append(name)
            elif path.exists():
                # Removal is represented in the manifest, applied only on confirmation.
                changed.append(name)
        if SecretScanner().scan_text(bundle, location='chatgpt-context'):
            raise ValueError('Posible secreto en el contexto; exportación bloqueada')
        manifest = {'schema_version': 1, 'definition_hash': _digest(_json(definition)),
                    'files': {p: _digest(c) for p, c in files.items() if p not in source_files and p != 'AGENTS.md'}}
        files[MANIFEST] = _json(manifest)
        if not manifest_path.exists() or _read(manifest_path) != files[MANIFEST]:
            changed.append(MANIFEST)
        return IntegrationPlan(files, tuple(changed), tuple(conflicts))

    def apply(self, *, confirmed: bool = False) -> IntegrationPlan:
        if not confirmed:
            raise PermissionError('Preparar el proyecto requiere confirmación')
        ExecutionGovernor().assert_allowed(GovernedAction.WRITE, build_execution_context(self.root))
        plan = self.plan()
        if plan.conflicts:
            raise ValueError('Archivos modificados por el usuario; resolver antes de regenerar: ' + ', '.join(plan.conflicts))
        for relative in plan.changed:
            path = project_path(self.root, relative)
            if relative not in plan.files:
                path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='') as handle:
                handle.write(plan.files[relative])
        return plan

    def check(self) -> dict:
        plan = self.plan()
        return {'ready': not plan.changed and not plan.conflicts,
                'changed': list(plan.changed), 'conflicts': list(plan.conflicts),
                'tools': ['codex', 'opencode'],
                'chatgpt': 'Requiere acceso al repositorio o adjuntar el contexto portable; sin herramientas solo propuestas.'}
