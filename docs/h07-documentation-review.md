# H07 · Revisión documental — 06/11/2026

Alcance: reconciliar las guías con el código integrado hasta H06
(`e23d54381c460f37b8ade59bbdcb267f2bbfe366`), los registros del laboratorio y los
issues de seguimiento. No se ha cambiado la lógica del producto.

## Correcciones

- [Estado vigente](project-status.md) con matriz de capacidades/evidencias,
  límites y mantenimiento por entrega. [Checklist](mvp-checklist.md) actual separado
  del [histórico](history/mvp-progress-through-2026-11-05.md), conservado sin usar
  sus cifras o pausas como estado actual.
- README: código 0.3.0 preparado, instalador no publicado, inicio externo,
  detección pasiva y selección natural aún pendiente de aceptación.
- CLI: entrypoint real, memoria-update funcional y distinción entre seguimiento
  nativo y modo orquestado capaz de iniciar agentes.
- Guía TUI: `factoria tui`; `factoria`/`ui` abren la web local.
- Memoria revisada y fechada, editores, roadmap y notas de distribución alineados.
- Una ayuda textual del shell web clásico decía que todo el flujo usaba un solo
  agente explícito. Ahora explica la selección de un agente compatible por etapa;
  no cambia selectores, handlers ni persistencia.
- #2 mantiene los nueve hitos implementados y la aceptación conjunta abierta.
  H07 puede cerrar su reconciliación documental; H05/H06 siguen abiertos.

## Evidencia de revisión

| Afirmación | Fuente contrastada |
| --- | --- |
| Entrada, web/TUI, updater frozen | `pyproject.toml`, `src/factoria/entrypoint.py` |
| Preparación y comandos nativos | `src/factoria/project_cli.py`, ayuda de CLI instalada |
| Memoria actualizable | `src/factoria/cli.py`, `_cmd_memory_update` |
| Agentes propios y roles por etapa | `application/agent_profiles.py`, `workflow_presets.py`, selectores web y pruebas existentes |
| Gates, snapshots y cierre | `application/native_workflow.py` y contrato directo |
| Host completado | H05: informe estructurado y registro de cierre con commits/aprobaciones |
| Paquetes y tests | H06: 335 tests Linux/Python 3.12.14 e informe de upgrade de 37 archivos |

Comprobaciones de esta entrega: `git diff --check`; existencia de los 67 enlaces
Markdown locales de los documentos modificados, incluidos destinos de fragmentos;
versión y ayuda de `project`/`native` de la CLI instalada; sintaxis de scripts inline
del HTML modificado con `node --check`. No se ha repetido la suite de 335 tests por
este cambio documental: esa cifra es evidencia de H06, no una ejecución nueva.
La revisión de sintaxis tampoco equivale a una prueba visual de navegador.

Actions permanece deshabilitado; no se ha solicitado ni ejecutado CI remoto,
instalador Windows o sesión autenticada de proveedor para esta entrega. La aceptación
externa, recuperación Windows y tag/release siguen pendientes en H05/H06.

## Mantenimiento posterior

Al entregar un hito, aplicar la lista de mantenimiento de
[project-status.md](project-status.md#mantener-el-estado). El cierre documental de
H07 no elimina esa obligación ni acepta por anticipado cambios futuros.
