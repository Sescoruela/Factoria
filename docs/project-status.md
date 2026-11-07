# Estado verificable de Factoria

Revisión: **07/11/2026**, sobre el código integrado hasta
`0fe34442e94bf5eb620b36a8682a87213ddff671` y la entrega H09 de ciclo de vida.
Esta página reúne el estado vigente; los registros fechados conservan su alcance original.

**0.3.0 preparada, sin tag ni release publicada. MVP todavía no aceptado.**
GitHub Actions está deshabilitado por petición del usuario desde el 05/11/2026,
hasta nuevo aviso. Las modificaciones de workflows no reactivan ese ajuste.

## Capacidades entregadas

| Capacidad | Implementación y comprobación | Evidencia |
| --- | --- | --- |
| Raíz del proyecto | Selección de subcarpetas sin duplicar la raíz del repositorio | [PR #4](https://github.com/Sescoruela/Factoria/pull/4) |
| Skills | Crear, editar, descartar y guardar Markdown; conflictos y referencias | [H02 #8](https://github.com/Sescoruela/Factoria/issues/8), [guía de editores](editor-milestones.md) |
| Agentes | Propios y básicos; instrucciones, skills y preferencias | [PR #5](https://github.com/Sescoruela/Factoria/pull/5), [H03 #9](https://github.com/Sescoruela/Factoria/issues/9) |
| Workflows | Propios basados en fix/feature, agente compatible por etapa, snapshots | [H01 #7](https://github.com/Sescoruela/Factoria/issues/7), [H04 #10](https://github.com/Sescoruela/Factoria/issues/10) |
| Integración | Preparación compartida y conservadora para ambas herramientas | [Contrato y comandos](direct-project-integration.md), [CLI](cli.md) |
| Seguimiento nativo | Etapas, evidencia, gates humanos, verificación/review, commit autorizado e historial | [Contrato nativo](direct-project-integration.md#recorrido-dentro-de-la-herramienta) |
| Inicio externo | UI/TUI con detección pasiva; el usuario inicia y autentica las herramientas | [Decisión y límites](memoria/decisiones.md) |
| Distribución | Wheel/sdist, checksums y actualización Python comprobados localmente; binario dirige al instalador | [H06 y límites](release-h06-status.md) |
| Plantillas H08 | Exportación JSON y preview/import conservador desde ambos shells y CLI; sin memoria/política/preferencias de máquina | [Uso y evidencia](project-templates.md) |
| Ciclo de vida H09 | Duplicar, revisar impacto, archivar y restaurar recursos con reservas y dependencias compatibles | [Uso y evidencia](resource-lifecycle.md) |

«Implementado» indica código y evidencia técnica. No afirma que una sesión nueva de
un LLM descubra la configuración o respete las instrucciones automáticamente.
Perfiles/modelos son preferencias; permisos, modelo efectivo y aislamiento de
agentes de una sesión externa siguen dependiendo de Codex/OpenCode.

## Qué demuestra cada comprobación

| Tipo | Última evidencia disponible | Qué queda fuera |
| --- | --- | --- |
| Pruebas deterministas | H09: **368 tests**, Linux/Python 3.12.14, correctos | Autenticación, selección natural y uso por un LLM |
| DOM/API | H04: tres smokes de los shells con Node/jsdom y API | Navegador real, inspección visual y experiencia completa del usuario; [H11 #17](https://github.com/Sescoruela/Factoria/issues/17) pendiente |
| Host con checkout | Fix y feature de laboratorio completados con agente/skill/workflow propios, aprobaciones y commits locales | Sesión externa independiente, descubrimiento natural y aislamiento de modelos; [evidencia H05](acceptance/h05-status.md) |
| Codex CLI/OpenCode autenticados | Pendiente de ejecución y registro | No se certifica por los tests, por un CLI presente ni por un manifiesto |
| Instalación Python | H06: actualización local 0.2.0→0.3.0, dos reaperturas y 37 archivos conservados | Upgrade Windows, todas las versiones históricas y UI visual; [informe](release-h06-smoke.json) |
| CI/Windows | Entregas anteriores tienen resultados en sus PR; H06 no ejecutado remotamente | No hay CI vigente ni instalador 0.3.0 validado; Actions deshabilitado |
| ChatGPT sin checkout | Contexto portable exportado | Recorrido conversacional en modo propuesta aún por registrar; no puede ejecutar sin herramientas |

Las cifras tienen fecha y alcance: no son contadores en tiempo real. Para comprobar
el código actual, ejecutar `python -m unittest discover -s tests` en un entorno instalado.
H07 reconcilió la documentación; su validación histórica está en [registro H07](h07-documentation-review.md).
H08/H09 añaden pruebas HTTP de ambos shells y controladores con DOM/API simulados. No hay validación visual nueva; el navegador disponible no pudo acceder al laboratorio local en H08.

## Pendientes y decisiones

| Elemento | Estado / siguiente comprobación |
| --- | --- |
| [H05 #11](https://github.com/Sescoruela/Factoria/issues/11) | Abierto: sesiones autenticadas, sesión nueva/ruta natural, casos negativos y modo propuesta sin checkout |
| [H06 #12](https://github.com/Sescoruela/Factoria/issues/12) | Abierto: Windows, actualización entre binarios, recuperación, CI, tag/release y descarga final |
| [H07 #13](https://github.com/Sescoruela/Factoria/issues/13) | Documentación reconciliada en esta entrega; mantenerla con cada cambio posterior |
| [Editor #2](https://github.com/Sescoruela/Factoria/issues/2) | Nueve hitos de implementación cubiertos; abierto por aceptación conjunta H05 |
| Reactivar Actions | Solo cuando el usuario lo pida; no se propone una fecha automática |
| Firma Authenticode | No disponible; checksums no equivalen a firma digital |
| H08 | Plantillas web/CLI implementadas; [guía, evidencia y límites](project-templates.md). H06 sigue pendiente |
| H09 | Duplicación, archivo reversible y restauración implementados; [guía y límites](resource-lifecycle.md) |
| H10–H13 | Evolución posterior en [roadmap](roadmap.md); no sustituye las pruebas de cierre del MVP |

La aceptación pendiente bloquea la declaración de MVP terminado. La documentación
de un procedimiento no significa que se haya ejecutado ni que su resultado sea correcto.

## Mantener el estado

Al cerrar o cambiar un hito:

1. Revisar comportamiento y comandos frente al código; actualizar las guías afectadas.
2. Registrar fecha, plataforma, alcance, resultado y enlace a PR/evidencia; distinguir
   tests, interfaz y sesiones reales. Mantener explícitos fallos y pasos no ejecutados.
3. Actualizar esta página, [checklist](mvp-checklist.md), memoria, roadmap y el issue
   correspondiente. #2 sigue abierto hasta la aceptación conjunta.
4. Actualizar notas de versión si cambia la distribución. No reactivar Actions ni
   afirmar release, firma o CI sin evidencia nueva.

El [histórico](history/mvp-progress-through-2026-11-05.md) conserva los estados
anteriores; no se utiliza como checklist vigente.
