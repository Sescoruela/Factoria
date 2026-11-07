<!-- factoria-memory: type=active | reviewed_commit=e06933195e3231bebacbe25aacaf19f529dc2164 | date=2026-11-07 | factoria=0.3.0 -->
# Arquitectura

## Objetivo
Factoría prepara y mantiene el sistema de trabajo por proyecto. El usuario conversa
principalmente con Codex/OpenCode, que consumen la configuración generada.

## Capas actuales
- `domain/`: entidades y reglas puras de flujo, permisos, feature y fix.
- `config/`: configuración global, organización, proyecto y resolución de políticas.
- `memory/`: detección, carga, renderizado, actualización y envejecimiento de memoria.
- `application/`: servicios de flujo, verificación, revisión, Git, historial y actualización.
- `application/skill_catalog.py`: skills Markdown versionables, creación exclusiva, guardado atómico y revisiones de catálogo.
- `application/project_integration.py`: compilación de configuración compartida a assets por herramienta.
- `application/project_relations.py`: lectura acotada y parcial de relaciones guardadas, reachability de recursos y vigencia de integración. Usa validadores puros de perfiles/etapas, configuración capturada y decodificación de skills sin reabrir sus fuentes.
- `application/resource_lifecycle.py`, `resource_archive.py`: duplicación, impacto de referencias, archivo reversible y restauración; reservas compartidas por editores/plantillas y registros versionables en `.factoria/archive/`.
- `application/project_templates.py`: bundles JSON v1 cerrados, preview ligado a catálogos/proyecto/contenido, importación conservadora y copia de recuperación en Git; sin copiar memoria ni políticas.
- `orchestration/workflows.py`: cada etapa conserva su rol de seguridad y puede seleccionar un agente del catálogo con `agent_id`.
- `application/native_workflow.py`: seguimiento directo sin llamadas LLM, con snapshots y evidencia.
- `application/agent_profiles.py`, `workflow_presets.py`: configuración versionable con lectura de formatos locales anteriores. El catálogo de agentes admite identificadores propios y un rol base. Los catálogos de agentes y workflows usan escritura atómica y revisión optimista para la edición web. Los workflows propios tienen identificador estable y un tipo base fix/feature; el seguimiento nativo congela ambos junto con la definición.
- `adapters/`, `orchestration/`: ejecución opcional de agentes externos detrás de contratos neutrales.
- `plugins/`: descubrimiento, compatibilidad, validación y ejecución de extensiones.
- `entrypoint.py`, `project_cli.py`, `web_app_n8n.py`, `web_editor_api.py`, `web_editor_state.py`: CLI, API y web local.
- `tools/release_artifacts.py`, `distribution_smoke.py`: herramientas de desarrollo para integridad y pruebas aisladas de paquetes; fuera del runtime del producto.

## Persistencia
- Compartida en Git: memoria, `config.toml`, `agents.json`, `workflows.json`, `.factoria/skills/*.md` y assets preparados.
- Temporal: `.factoria/work/<id>/`, excluido localmente del control de versiones.
- Historial local: ruta de Git `factoria/history`, hasta 50 registros o 30 días.
- Configuración de máquina/modelos y rutas de ejecutables: entorno personal, fuera del proyecto.

## Límites
La selección natural del flujo depende del agente anfitrión. Las comprobaciones del
CLI controlan el avance registrado; los permisos y sandbox de la sesión controlan
sus acciones externas. ChatGPT sin checkout recibe un contexto portable y propone;
no puede afirmar ejecución. Ver `docs/direct-project-integration.md`.

El entrypoint bloquea update/rollback por pip en ejecutables frozen; la actualización
del binario usa el instalador. La versión canónica está en pyproject.toml y los
metadatos de release se incluyen como recurso del paquete. Estado actual y pruebas:
[registro vigente](../project-status.md).

## Pruebas de navegador H11

`tests/ui/browser/` contiene Playwright fijado y dos servidores reales con HOME/Git
desechables. Se distribuye fuera del runtime. La API compartida devuelve el estado
completo de editores tras sus operaciones, conservando los campos base. Informes,
trazas y CI pendiente: [guía](../browser-smoke.md).

H12: no se inyectan parches Python en HTML. Assets JS/CSS y servicios compartidos
de estado/API descritos en [frontend](../frontend.md). La vista n8n es principal;
la clásica es compatibilidad.

H13: `application/config_schema.py` aplica gates de versión; `config_recovery.py`
previsualiza/migra/checkpoint/restaura con copias locales en metadatos Git y journal
recuperable. El panel `configuration.js` y CLI comparten el servicio autenticado y
con políticas. Snapshots/memoria/historial quedan fuera del inventario. [Guía](../configuration-recovery.md).
