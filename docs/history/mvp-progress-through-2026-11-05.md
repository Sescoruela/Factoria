# Archivo histórico: progreso hasta H05

Registro conservado de entregas anteriores. Las cifras, bloqueos y estados de este
archivo describen aquellos momentos; no son el estado actual. Consultar
[estado vigente](../project-status.md) y [checklist actual](../mvp-checklist.md).

# Cierre del MVP

## Objetivo acordado

Configurar y mantener la estructura completa de trabajo de cada proyecto desde
Factoría, para usar sus agentes, instrucciones, skills, memoria y flujos directamente
desde Codex u OpenCode. El LLM se utiliza principalmente en esas herramientas.

## Criterios y evidencia

| Hito | Estado en esta entrega | Evidencia |
| --- | --- | --- |
| Inicio externo de Codex/OpenCode | Implementado; detección pasiva en UI | `tool_presence.py`, límites de API/TUI y pruebas de regresión |
| Edición completa: añadir, modificar y guardar recursos | Agentes, skills, asignaciones y workflows propios implementados; aceptación autenticada pendiente | `docs/editor-milestones.md` |
| Configuración compartida por proyecto | Implementado | `agents.json`, `workflows.json`, `config.toml`; migración de configuración local anterior |
| Instrucciones y skills por rol | Implementado | Editor web, validación de rutas y propagación a uso directo/orquestado |
| Preparación para ambas herramientas | Implementado | Skills compartidas, comandos y agentes OpenCode, bloque de entrada en AGENTS.md |
| Seguimiento sin otra sesión LLM | Implementado | CLI `native`; fix/feature, snapshots, evidencia, pausas, aprobaciones y cierre |
| Verificación y review bloqueantes | Implementado | Comandos confirmados, alternativa manual y contrato JSON de review |
| Regeneración conservadora | Implementado | Preview, hashes, conflictos, preservación de AGENTS.md y retirada de assets deshabilitados |
| Pruebas deterministas | 270 pruebas en la entrega de agentes; resultados de nuevas entregas registrados por PR | `tests/test_project_integration.py` y suite existente |
| CI multiplataforma | Configurado; resultado de ejecución registrado en GitHub | Ubuntu Python 3.11–3.13; Windows/macOS Python 3.11 |
| Instalador Windows | Pipeline existente; resultado de build registrado en GitHub | Build, instalación, smoke de versión y desinstalación en CI |
| Aceptación con Codex autenticado | Pendiente: CLI ausente en este entorno | Ejecutar el recorrido real documentado |
| Aceptación con OpenCode autenticado | Pendiente: CLI ausente en este entorno | Ejecutar el recorrido real documentado |
| Codex/ChatGPT con checkout | Parcial: fix listo para commit; feature esperando aprobación de plan | Comprobar acceso a archivos y CLI, y comportamiento ante ausencia de herramientas |
| ChatGPT sin checkout | Contexto portable implementado | Modo propuesta; no equivale a ejecución de flujos |

El estado «implementado» significa que existe código y una comprobación determinista;
no demuestra aceptación con un proveedor remoto. El cierre funcional completo requiere
la aceptación real en ambas herramientas y CI verde sobre el cambio revisado.

## Fuera del MVP

- Firma Authenticode y distribución amplia: requiere certificado y custodia de firma.
- Invocar APIs LLM propias o custodiar credenciales de proveedores dentro de Factoría.
- Flujos arbitrarios con ramificaciones y selección automática del modelo de una sesión externa o aislamiento no provisto por ella.
- Stash automático, push/PR automáticos, catálogo central de proyectos y métricas inventadas.

## Registro de aceptación real

| Entorno | Versión herramienta/modelo | Fix | Feature y aprobaciones | Bloqueos | Resultado |
| --- | --- | --- | --- | --- | --- |
| Codex local | Desconocidos | No ejecutado | No ejecutado | CLI ausente | Pendiente |
| OpenCode local | Desconocidos | No ejecutado | No ejecutado | CLI ausente | Pendiente |
| Host actual ChatGPT/Codex con checkout | No expuestos | Parcial: 3 pruebas OK, ready_for_commit | Plan preparado; bloqueo sin aprobación observado | Aprobaciones, sesión nueva y finalización | No aceptado |

## Verificación local de esta entrega · 03/11/2026

- Suite completa: **244 pruebas, OK** (`python -m unittest discover -s tests`).
- Sintaxis del JavaScript de la nueva interfaz: comprobada con `node --check`.
- Diff: sin errores de whitespace con `git diff --check`.
- Runtime: sin nuevas dependencias externas obligatorias.
- Codex/OpenCode no están instalados en el entorno de esta revisión; no se han
  ejecutado sesiones autenticadas ni se ha validado el enrutado natural por un LLM.
- CI y build Windows de esta entrega: consultar los resultados del [PR #1](https://github.com/Sescoruela/Factoria/pull/1).

## Ampliación del editor · 04/11/2026

Los nueve hitos de skills/agentes/workflows están planificados en `editor-milestones.md`. No se declaran completados por la existencia de edición parcial de roles y fix/feature. El cierre de esa ampliación exige el recorrido completo de creación, edición, guardado y recuperación desde la herramienta externa.

## Verificación del arranque externo · 04/11/2026

- Suite local: **251 pruebas, OK**.
- Regresión: refrescos HTTP repetidos, preferencias, dashboard TUI y endpoints bloqueados sin ejecutar proveedores.
- JavaScript: sintaxis de ambas interfaces web y del parche comprobada.
- Los nueve hitos del editor están pendientes/parciales y registrados en el [issue #2](https://github.com/Sescoruela/Factoria/issues/2).

## Roadmap acordado · 05/11/2026

Ver `roadmap.md` y el [issue #6](https://github.com/Sescoruela/Factoria/issues/6): H01–H07 coordinan el cierre del MVP; H08–H13 se reservan para después. Las cifras de pruebas fechadas anteriores son evidencia histórica. La PR #5 tiene 270 pruebas y CI/instalador correctos; la aceptación autenticada sigue pendiente.

## H01 · Guardado seguro de workflows

Protección implementada: revisión optimista, identidad del proyecto, escritura atómica y borradores conservados ante conflictos. Ver #7 para evidencia de CI y cierre. Suite local: 279 pruebas correctas; sintaxis JavaScript y comprobaciones DOM/API en ambas interfaces correctas. La aceptación autenticada continúa pendiente.

## H02 · Catálogo de skills

Editor web y persistencia Markdown implementados; ver #8 para evidencia de CI y cierre. Creación, edición, descarte y guardado con control de conflictos, selector de skills en agentes, catálogo compartido y contexto portable. H03 se registra en su sección; H04 se registra en su sección; la aceptación autenticada sigue pendiente.

## H03 · Agentes propios por etapa

Selección por `agent_id` con validación de rol base, herencia de instrucciones, skills
y preferencias y overrides por etapa. Se conserva la compatibilidad con snapshots
anteriores y los controles del rol. Ver #9 para evidencia de pruebas y CI. Los
recorridos deterministas no equivalen a aceptación autenticada; H04 se registra en su sección; H05 sigue pendiente.

## H04 · Workflows propios

Catálogo completo por identificador, editor de creación/edición, CLI y recursos
preparados para ambas herramientas implementados. Se conservan tipos base,
aprobaciones, políticas, referencias, conflictos y snapshots. Ver #10 para evidencia
de pruebas y CI. El cierre de los editores no sustituye la aceptación real H05 ni
la primera versión distribuible H06; el seguimiento documental H07 continúa.

## H05 · Aceptación real en curso

El [estado observado](../acceptance/h05-status.md) distingue el recorrido parcial del
agente anfitrión actual de las sesiones autenticadas externas, todavía pendientes.
El [protocolo](../acceptance/h05-protocol.md) y `tools/acceptance_lab.py` preparan seis
repositorios nuevos y un informe pendiente; no inician proveedores ni certifican
autenticación/modelos/aprobaciones. La feature está detenida por su aprobación de
plan y el fix espera autorización de commit local. H05 #11 permanece abierto; H06
no se considera desbloqueado por las pruebas deterministas.
