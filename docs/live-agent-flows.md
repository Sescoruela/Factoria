# Modo opcional: flujos orquestados con agentes

Para trabajar directamente dentro de Codex/OpenCode, consultar `direct-project-integration.md`. Este documento describe el lanzamiento de agentes desde Factoria.

Este hito conecta la CLI de Factoria con el orquestador de agentes, los adaptadores Codex/OpenCode y la verificación segura ya existente.

## Inicio

`factoria fix` y `factoria feature` dejan de limitarse a crear un workspace: ahora pueden ejecutar las etapas reales del flujo.

- Todo flujo necesita memoria de proyecto inicializada.
- Factoria no modifica `main` directamente.
- Si el usuario está en `main`, debe indicar `--branch <nombre>` y Factoria crea esa rama local.
- El árbol de trabajo debe estar limpio antes de iniciar el flujo.
- No se hace `push`, no se abre PR y no se realiza commit automáticamente.

Ejemplos:

```text
factoria fix "Corrige el cálculo de IVA" --branch fix/iva
factoria fix "Refactor grande" --branch refactor/facturacion --large
factoria feature "Añade exportación CSV" --branch feature/csv
```

`--tool codex|opencode` define una preferencia, no una obligación. El orquestador puede usar un fallback cuando la herramienta preferida no cumple las capacidades o la política de seguridad requeridas.

## Gobernanza

Un fix pequeño ejecuta:

1. explorer;
2. implementer;
3. verificaciones confirmadas de Factoria;
4. reviewer.

Al terminar queda pausado en `ready_for_commit` para que el usuario inspeccione y haga el commit manualmente.

Una feature y un fix `--large` ejecutan primero explorer + planner y quedan en `awaiting_plan_approval`. El usuario revisa `.factoria/work/<flow>/plan.md` y continúa explícitamente:

```text
factoria resume <flow-id> --approve-plan
```

Después de implementación, verificación y review quedan en `awaiting_final_approval`:

```text
factoria resume <flow-id> --approve-final
```

Si hay cambios pendientes, el flujo pasa a `ready_for_commit`. Tras hacer el commit manualmente, `factoria resume <flow-id>` puede cerrar el flujo cuando el árbol esté limpio.

## Seguridad de adaptadores

Los roles de análisis (`explorer`, `planner`, `reviewer` y `documenter`) se ejecutan en modo de solo lectura. `documenter` produce una propuesta en `memory-proposal.md`; no edita la memoria por sí mismo.

En el perfil normal integrado en este hito:

- Codex se admite para roles de solo lectura con sandbox read-only y sin escalado de aprobaciones.
- Codex no se usa como implementer porque Factoria todavía no puede interceptar de forma suficientemente granular operaciones destructivas dentro del workspace.
- OpenCode se usa como implementer con edición del proyecto permitida y resto de herramientas denegadas mediante `OPENCODE_CONFIG_CONTENT`; especialmente, el shell queda bloqueado.
- Build, test, lint, typecheck y smoke no los ejecuta el agente: los ejecuta `SafeCheckExecutor` únicamente desde comandos confirmados en memoria.

Si no existe una ruta compatible con estas restricciones, el flujo se bloquea en lugar de relajar permisos.

## Modelos

Los agentes siguen solicitando perfiles abstractos `rapido`, `equilibrado` y `potente`. El entorno puede mapearlos a modelos concretos sin cambiar el flujo:

```text
FACTORIA_CODEX_RAPIDO
FACTORIA_CODEX_EQUILIBRADO
FACTORIA_CODEX_POTENTE
FACTORIA_OPENCODE_RAPIDO
FACTORIA_OPENCODE_EQUILIBRADO
FACTORIA_OPENCODE_POTENTE
```

Si no existe un mapeo, la etapa se bloquea; ver `deterministic-model-routing.md`.

## Artefactos

Cada ejecución persiste temporalmente en `.factoria/work/<flow-id>/`:

- `task.md`
- `explore.txt`
- `plan.md` cuando aplica
- `verification.md`
- `review.md`
- `memory-proposal.md` cuando aplica
- `agents.log`
- `agent-flow.json`
- `state.toml`

`agents.log` registra rol, intento, adaptador, perfil, modelo, fallback y resultado sin persistir secretos.

## Límites actuales

- El reviewer se valida con el contrato estructurado y sus hallazgos bloqueantes impiden el cierre. Ver `structured-review-loop.md`.
- La confirmación de commit y su preview están disponibles mediante `factoria commit`.
- El historial local conserva informes de ejecuciones finalizadas; ver `final-report-history-metrics.md`.
- Las pruebas herméticas verifican la orquestación con un agente simulado. La aceptación con proveedores reales se registra aparte.
