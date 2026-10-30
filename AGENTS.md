<!-- factoria-memory: type=active | reviewed_commit=aeb008a5b4fcfeb295c0303750f4742097a9d4fa | date=2026-10-30 | factoria=0.1.0 -->
# Factoria

## Propósito
Factoría extensible y portable para orquestar desarrollo asistido por agentes con memoria persistente, validaciones, permisos, plugins y trazabilidad.

## Tecnologías
- Python >= 3.11
- Biblioteca estándar como dependencia de runtime

## Módulos
- **domain**: `src/factoria/domain/`
- **config**: `src/factoria/config/`
- **plugins**: `src/factoria/plugins/`
- **memory**: `src/factoria/memory/`

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
