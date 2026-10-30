<!-- factoria-memory: type=active | reviewed_commit=aeb008a5b4fcfeb295c0303750f4742097a9d4fa | date=2026-10-30 | factoria=0.1.0 -->
# Arquitectura

## Capas actuales
- `src/factoria/domain/`: entidades, contratos y reglas puras.
- `src/factoria/config/`: carga y resolución de configuración global/proyecto.
- `src/factoria/plugins/`: descubrimiento, validación y prioridad de plugins.
- `src/factoria/memory/`: inicialización, renderizado, persistencia inicial y staleness de memoria.

## Principios
- Núcleo agnóstico de herramientas concretas.
- Tipado fuerte e inmutabilidad por defecto.
- Biblioteca estándar en runtime.
- Integraciones externas detrás de adaptadores o plugins.
- La memoria del proyecto vive junto al código y `AGENTS.md` actúa como índice corto.

## Memoria de proyecto
`memoria-init` trabaja en dos fases: propone y después exige confirmación antes de escribir. Los proyectos activos reciben memoria profunda; los de mantenimiento reciben una ficha compacta y documentación de verificación.

## Dependencias internas
- `config` depende de `domain`.
- `plugins` depende de `domain` y `config`.
- `memory` depende de `domain`; sus detectores usan filesystem y Git como infraestructura ligera.
