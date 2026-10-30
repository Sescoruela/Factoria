# Memoria persistente de proyecto

La memoria evita reexplorar un repositorio completo en cada tarea. El punto de entrada es `AGENTS.md`; la información extensa vive en `docs/memoria/` y solo se consulta cuando es relevante.

## Estructura

```text
repo/
├── .factoria/config.toml
├── AGENTS.md
└── docs/
    └── memoria/
        ├── arquitectura.md
        ├── flujos.md
        ├── decisiones.md
        └── testing.md
```

Los proyectos de mantenimiento generan únicamente `AGENTS.md` y `testing.md` como base. Los proyectos activos mantienen también arquitectura, flujos y decisiones.

## memoria-init

`MemoryInitializer` no escribe directamente. Primero construye una `MemoryInitProposal` con:

- tecnologías detectadas;
- módulos propuestos;
- actividad Git de los últimos 30 días;
- clasificación sugerida `active` o `maintenance`;
- commit de referencia y versión de Factoria.

La propuesta debe confirmarse antes de pasarse al escritor de filesystem. `write_initial_memory` se niega a sobrescribir archivos de memoria existentes.

## Detección inicial

Los detectores por defecto son conservadores:

- `.sln` / `.csproj` → .NET;
- `angular.json` → Angular;
- `package.json` → JavaScript/TypeScript;
- `pyproject.toml` / `requirements*.txt` → Python;
- carpetas convencionales como `backend/`, `frontend/`, `shared/` o `contracts/` → módulos propuestos.

La clasificación por Git usa una ventana de 30 días. Los umbrales iniciales del adaptador son configurables y deberán ajustarse con uso real; la clasificación se presenta como propuesta antes de persistirse.

## Envejecimiento

Cada documento puede tener un umbral distinto de commits desde su última revisión. Valores por defecto actuales:

- arquitectura: 25;
- flujos: 15;
- decisiones: 50;
- testing: 20.

Los valores pueden sobrescribirse en `.factoria/config.toml` mediante `[memory.staleness]`.

Superar un umbral no reescribe nada automáticamente: marca el documento como candidato a revisión para el futuro flujo `memory-update`.
