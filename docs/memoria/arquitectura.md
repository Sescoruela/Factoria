<!-- factoria-memory: type=active | reviewed_commit=1a2e02c9692177fb5c7d63a10efa70379b5dca17 | date=2026-11-03 | factoria=0.2.0 -->
# Arquitectura

## Objetivo
Factoría prepara y mantiene el sistema de trabajo por proyecto. El usuario conversa
principalmente con Codex/OpenCode, que consumen la configuración generada.

## Capas actuales
- `domain/`: entidades y reglas puras de flujo, permisos, feature y fix.
- `config/`: configuración global, organización, proyecto y resolución de políticas.
- `memory/`: detección, carga, renderizado, actualización y envejecimiento de memoria.
- `application/`: servicios de flujo, verificación, revisión, Git, historial y actualización.
- `application/project_integration.py`: compilación de configuración compartida a assets por herramienta.
- `application/native_workflow.py`: seguimiento directo sin llamadas LLM, con snapshots y evidencia.
- `application/agent_profiles.py`, `workflow_presets.py`: configuración versionable con lectura de formatos locales anteriores.
- `adapters/`, `orchestration/`: ejecución opcional de agentes externos detrás de contratos neutrales.
- `plugins/`: descubrimiento, compatibilidad, validación y ejecución de extensiones.
- `entrypoint.py`, `project_cli.py`, `web_app_n8n.py`, `web_n8n_patch.py`: CLI, API y web local.

## Persistencia
- Compartida en Git: memoria, `config.toml`, `agents.json`, `workflows.json` y assets preparados.
- Temporal: `.factoria/work/<id>/`, excluido localmente del control de versiones.
- Historial local: ruta de Git `factoria/history`, hasta 50 registros o 30 días.
- Configuración de máquina/modelos y rutas de ejecutables: entorno personal, fuera del proyecto.

## Límites
La selección natural del flujo depende del agente anfitrión. Las comprobaciones del
CLI controlan el avance registrado; los permisos y sandbox de la sesión controlan
sus acciones externas. ChatGPT sin checkout recibe un contexto portable y propone;
no puede afirmar ejecución. Ver `docs/direct-project-integration.md`.
