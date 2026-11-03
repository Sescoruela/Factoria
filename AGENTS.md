<!-- factoria-memory: type=active | reviewed_commit=1a2e02c9692177fb5c7d63a10efa70379b5dca17 | date=2026-11-03 | factoria=0.2.0 -->
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
- No confundir las pruebas deterministas con aceptación en una sesión real de Codex/OpenCode.
