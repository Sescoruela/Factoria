<!-- factoria-memory: type=active | reviewed_commit=999bb373751a8cc7445dfe5ad5381809d2517028 | date=2026-11-07 | factoria=0.3.0 -->
# Factoria

## Propósito
Configurar y mantener agentes, instrucciones, skills, flujos, políticas y memoria por proyecto para trabajar principalmente desde Codex u OpenCode. La aplicación prepara ambas integraciones; el CLI conserva seguimiento y verificación sin iniciar otro LLM en el modo directo.

## Tecnologías
- Python >= 3.11
- Biblioteca estándar como dependencia de runtime

## Módulos
- **domain**: `src/factoria/domain/`
- **config**: `src/factoria/config/`
- **plugins**: `src/factoria/plugins/`
- **memory**: `src/factoria/memory/`
- **application**: `src/factoria/application/`
- **adapters**: `src/factoria/adapters/`
- **orchestration**: `src/factoria/orchestration/`
- **interfaces**: `src/factoria/entrypoint.py`, `src/factoria/project_cli.py`, `src/factoria/web_app_n8n.py`

## Comandos confirmados
- **test**: `python -m unittest discover -s tests`

## Reglas obligatorias
- El núcleo debe permanecer agnóstico de Codex, OpenCode, GitHub u otras herramientas concretas.
- No introducir dependencias de runtime externas sin una decisión explícita.
- Mantener compatibilidad con Python 3.11 o superior.
- No incluir secretos, tokens, credenciales ni información corporativa.

## Dependencias
- `memory` usa contratos y modelos de `domain`.
- `config` usa modelos de `domain` y configuración de memoria.
- Integraciones concretas deben vivir fuera del dominio.

## Memoria detallada
- Arquitectura: `docs/memoria/arquitectura.md`
- Flujos: `docs/memoria/flujos.md`
- Decisiones: `docs/memoria/decisiones.md`
- Verificación: `docs/memoria/testing.md`

## Uso por agentes
Consulta primero este archivo y abre solo la memoria detallada relevante para la tarea.
Si el código contradice comportamiento o estructura descritos aquí, marca la memoria como potencialmente desactualizada.
Las reglas obligatorias no se ignoran automáticamente aunque el código actual las contradiga.

## Integración directa
- Objetivo y contrato: `docs/direct-project-integration.md`.
- Criterios de cierre: `docs/mvp-checklist.md`.
- Plantillas portables web/CLI: `docs/project-templates.md`; preview y confirmación sin sobrescribir recursos en conflicto.
- Ciclo de vida de recursos: `docs/resource-lifecycle.md`; referencias bloqueantes, archivo reversible y snapshots conservadas. No reutilizar IDs archivados sin restaurar.
- Mapa de configuración guardada: `docs/project-relations.md`; diagnóstico de solo lectura y navegación a editores sin descartar borradores.
- Frontend: `docs/frontend.md`; lógica en assets, servicios de edición compartidos y vista principal n8n.
- Smoke real y evidencia local/CI pendiente: `docs/browser-smoke.md`. Node/Playwright solo son dependencias de desarrollo; no reactivar Actions para ejecutar la suite.
- No confundir las pruebas deterministas con aceptación en una sesión real de Codex/OpenCode.
- Estado vigente y límites: `docs/project-status.md`. Código 0.3.0 preparado; no hay release publicada ni aceptación externa completa.
- GitHub Actions está deshabilitado por petición del usuario hasta nuevo aviso; no reactivarlo como parte de una tarea.
- Al cerrar hitos, actualizar guías, evidencia fechada, checklist, roadmap e issues. H05/H06 permanecen abiertos; no trasladar estados antiguos al presente.
