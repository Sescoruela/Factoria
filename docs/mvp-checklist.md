# Cierre del MVP

Estado al **06/11/2026**. Referencia vigente: [estado y evidencia](project-status.md).
Factoria configura agentes, skills, workflows, políticas y memoria por proyecto;
el trabajo LLM se realiza principalmente desde Codex/OpenCode iniciados externamente.

## Implementación

- [x] Inicio externo: detección pasiva en UI/TUI y bloqueo de lanzamiento desde la aplicación.
- [x] Añadir, modificar, descartar y guardar skills/agentes/workflows propios.
- [x] Agentes compatibles por etapa, herencia/overrides y snapshots congeladas.
- [x] Configuración compartida, validación, migración conservadora, revisiones y escritura atómica.
- [x] Preparación para ambas herramientas, hashes y conflictos sin sobrescribir contenido propio.
- [x] Seguimiento nativo sin segunda sesión LLM; verificación, review y gates humanos.
- [x] Contexto portable para conversaciones sin checkout, limitado a propuestas.
- [x] Documentación reconciliada con las capacidades y evidencias disponibles (H07).

Implementación no equivale a aceptación autenticada. Detalle: [editores](editor-milestones.md),
[contrato directo](direct-project-integration.md), [CLI](cli.md) y [roadmap](roadmap.md).

## Aceptación y distribución pendientes

- [ ] H05: completar fix/feature en sesiones autenticadas de Codex CLI y OpenCode;
  registrar versiones/modelos, carga de configuración, selección natural/explicita,
  aprobaciones y casos negativos con Factoria cerrada.
- [ ] H05: registrar descubrimiento desde sesión nueva y conversación sin checkout
  en modo propuesta; no afirmar ejecución sin herramientas.
- [ ] H06: validar instalador y actualización entre binarios en Windows, reapertura
  visual, conservación de configuración y recuperación desde copia.
- [ ] H06: CI multiplataforma de la entrega candidata, tras autorización del usuario
  para reactivar Actions. Actualmente deshabilitado hasta nuevo aviso.
- [ ] H06: tag y release del commit validado, artefactos identificables, checksums y
  descarga final verificada. No hay release 0.3.0 publicada ni firma Authenticode.
- [ ] #2: aceptar el recorrido conjunto de los nueve editores en las herramientas reales.

## Evidencia ya observada

| Comprobación | Resultado y alcance | Registro |
| --- | --- | --- |
| Suite determinista | H09: 368 tests correctos en Linux/Python 3.12.14 | [Ciclo de vida y límites](resource-lifecycle.md) |
| Interfaz | Smokes DOM/API históricos; sin validación de navegador real en esta entrega | [Memoria de pruebas](memoria/testing.md) |
| Host con checkout / fix | Completado tras autorización; 3 pruebas, review y commit local | [H05](acceptance/h05-status.md) |
| Host con checkout / feature | Plan y resultado aprobados; 7 pruebas, aceptación, review y commit local; completado | [Cierre de feature](acceptance/evidence/host-feature/completion.json) |
| Python / paquetes | Wheel/sdist, recursos y checksums; upgrade aislado con dos reaperturas y 37 archivos conservados | [Informe H06](release-h06-smoke.json) |
| CI e instalador Windows | Resultados anteriores en sus PR; no ejecutados para H06/H07 por petición del usuario | [Estado vigente](project-status.md) |

Los dos recorridos anfitriones son del mismo agente secuencial y no prueban
sesiones independientes, autenticación de CLI, selección natural ni aislamiento de modelos.
Las observaciones de ausencia de CLIs del 05/11 son históricas, no un inventario
actual del equipo. Presencia y autenticación se registran de nuevo al ejecutar H05.

## Fuera del MVP

- Custodiar credenciales o invocar APIs LLM propias desde la aplicación.
- Flujos arbitrarios con ramificaciones; cambio automático de modelo o aislamiento
  no proporcionado por la herramienta externa.
- Stash, push o PR automáticos y métricas de aceptación inventadas.
- Firma Authenticode y distribución amplia de confianza sin certificado/custodia adecuados.

## Seguimiento

H01–H04 están completados; H05/H06 siguen abiertos. H07 reconcilia la documentación
actual y establece su mantenimiento por entrega. [#2](https://github.com/Sescoruela/Factoria/issues/2)
conserva la aceptación conjunta; [#6](https://github.com/Sescoruela/Factoria/issues/6)
coordina el roadmap. Las cifras y estados antiguos están en el
[archivo histórico](history/mvp-progress-through-2026-11-05.md), sin sobrescribir
las evidencias originales. El MVP solo se declara terminado al completar los
criterios de aceptación y distribución anteriores.
