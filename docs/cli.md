# CLI de Factoria

Entrada instalada: `factoria = factoria.entrypoint:main` (pyproject.toml).
También disponible como `python -m factoria`. Requiere el paquete instalado.
Estado del producto y evidencia: [estado vigente](project-status.md).

## Elegir el modo

`factoria --project /ruta/proyecto --read-only project relations` consulta las
relaciones y diagnósticos sin modificar fuentes. Para interpretar sus estados y
límites ver [mapa del proyecto](project-relations.md).

| Modo | Comandos | Efecto |
| --- | --- | --- |
| Web local | `factoria`, `factoria ui`, `factoria web` | Configurar proyectos sin iniciar proveedores |
| Terminal | `factoria tui`, `factoria onboarding` | Interfaz/guía con detección pasiva |
| Directo, principal | `factoria project …`, `factoria native …` | Preparar ambas herramientas y seguir el flujo dentro de una sesión externa, sin otro LLM |
| Orquestado, opcional | `factoria fix …`, `factoria feature …` | Puede iniciar agentes por adaptadores; solo desde terminal externa explícita |
| Actualización Python | `factoria update`, `factoria rollback` | Preview y confirmación explícita; procedencia por commit |
| Binario Windows | Instalador de la versión verificada | No utiliza pip; update/rollback muestran instrucciones |

La UI/TUI no permite usar sus consolas/endpoints para iniciar agentes. Push y PR
no son automáticos en el producto. No mezclar comandos de reanudación/cierre del
modo orquestado con los del modo nativo.

## Preparar y comprobar un proyecto

Desde un repositorio Git con memoria y configuración guardadas:

```bash
factoria --project /ruta/proyecto project workflows
factoria --project /ruta/proyecto project prepare
# Revisar preview y conflictos antes de autorizar escritura:
factoria --project /ruta/proyecto project prepare --yes
factoria --project /ruta/proyecto project check
```

`--project` va antes del subcomando y localiza la raíz desde subcarpetas.
`project check` devuelve `ready`, cambios y conflictos; sale con código 1 si no
está listo. La preparación no modifica configuración global de Codex/OpenCode.
Se guardan primero los editores; después se regeneran las integraciones.

## Seguimiento desde Codex/OpenCode

El usuario abre y autentica la herramienta fuera de Factoria. La skill preparada
guía los comandos siguientes; el agente escribe los artefactos que indique el JSON:

```bash
factoria --project /ruta/proyecto native start fix --tool codex --task "Corregir error de cálculo"
factoria --project /ruta/proyecto native status <flow-id>
factoria --project /ruta/proyecto native next <flow-id>
factoria --project /ruta/proyecto native pause <flow-id>
factoria --project /ruta/proyecto native resume <flow-id>
```

Para OpenCode usar `--tool opencode`; para un workflow propio sustituir `fix` por
su identificador listado por `project workflows`. Cada etapa conserva su rol base.
`native next` no realiza la implementación por sí mismo: valida evidencia y avanza;
en verify ejecuta las comprobaciones confirmadas. Ver [contrato de etapas](direct-project-integration.md#recorrido-dentro-de-la-herramienta).

Las aprobaciones `--approve-plan`/`--approve-final` se utilizan solo después de
que el usuario vea y apruebe ese resultado, en su etapa correspondiente. No se
anticipan por haber pedido inicialmente una tarea. El commit requiere autorización
posterior; se realiza con Git y `native finish <flow-id>` exige árbol limpio con
el contenido verificado. Cancelación: `native cancel <flow-id> --yes`; conserva
código y rama. No hay stash, reset ni borrado de ramas automáticos.

## Memoria, estado y modo avanzado

- `factoria --project /ruta/proyecto memoria-init`: propone memoria; escritura con confirmación.
- `factoria --project /ruta/proyecto memoria-update`: carga la memoria existente y muestra propuesta; `--yes` confirma los cambios revisados.
- `factoria --project /ruta/proyecto status`: diagnóstico operativo, memoria y flujos.
- `factoria fix`/`feature`: modo avanzado; puede crear una rama y ejecutar agentes.
  Consultar sus argumentos y límites en [flujos orquestados](live-agent-flows.md).
- `factoria resume`/`cancel`: ciclo de vida del modo avanzado; para uso directo utilizar `native`.

`--read-only` rechaza las operaciones de escritura; no es una manera de saltarse
aprobaciones ni equivale al sandbox de la herramienta externa. Las políticas del
proyecto, revisión y controles de secretos siguen aplicándose.

## Plantillas entre proyectos

`factoria project templates export --name "Equipo" --output equipo.json` exporta
configuración guardada sin datos de máquina. `factoria project templates import
equipo.json` muestra el preview; aplicar exige `--yes --token TOKEN_DEL_PREVIEW`.
Usar `--project` antes del subcomando para elegir origen/destino. Un conflicto
bloquea toda la importación. Ver [plantillas](project-templates.md).

## Actualización de Factoria

[Guía de actualización y rollback](update-rollback.md) para Python con procedencia
verificada. [Guía de distribución](release-process.md) para checksums, copia de
configuración y reinstalación del binario. 0.3.0 está preparada; no se ha publicado
una release ni reactivado Actions. No ejecutar comandos de actualización de ejemplo
sin un artefacto/tag disponible y verificado.

## Ciclo de vida de recursos

`factoria project resources list` muestra recursos activos y registros.
`factoria project resources duplicate agent reviewer --new-id reviewer-api` propone
una copia; `archive workflow fix-api` propone archivar; `restore workflow ID_DE_ARCHIVO`
propone restaurar un registro. Prefijar estos últimos con `factoria project resources`.
Aplicar repitiendo con `--yes --token TOKEN_DEL_PREVIEW` después de revisar el impacto.
Consultar [reglas, referencias y recuperación](resource-lifecycle.md).
