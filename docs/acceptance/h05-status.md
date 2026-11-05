# H05 · Estado observado el 05/11/2026

**Parcial; no aceptado.** La prueba se realizó desde el agente anfitrión actual de
ChatGPT/Codex Work con checkout y shell, sobre repositorios sintéticos aislados.
No es una ejecución de Codex CLI ni de OpenCode ni una sesión nueva de descubrimiento.

| Entorno / caso | Resultado observado | Pendiente |
| --- | --- | --- |
| Codex CLI local / fix y feature | CLI ausente en este entorno | Instalación/sesión autenticada externa, versión/modelo y recorrido completo |
| OpenCode local / fix y feature | CLI ausente en este entorno | Instalación/sesión autenticada externa, versión/modelo y recorrido completo |
| Host actual con checkout / fix-lab | Agente y skill cargados; dos fallos iniciales; tres pruebas finales correctas; review registrada; pausado en ready_for_commit | Autorización del commit local y finish; sesión nueva y ruta natural |
| Host actual con checkout / feature-lab | Tres pruebas base correctas; función nueva ausente; plan redactado; avanzar sin aprobación devuelve error; pausado en approve_plan | Aprobación posterior del plan, implementación y resto del recorrido |
| ChatGPT sin checkout | No ejecutado | Conversación nueva con solo contexto portable y comprobación de modo propuesta |

La versión del host y el modelo no están expuestos en esta sesión y se registran como
**desconocidos**. Los perfiles de los agentes son preferencias, no versiones de modelo.
El CLI de Factoria se hizo accesible temporalmente mediante el entorno virtual para
los comandos de la prueba; no se alteró PATH global ni se inició otro proveedor.

## Evidencias revisables

- [Informe estructurado](h05-observed-2026-11-05.json), con fuente revisada y límites.
- [Exploración del fix](evidence/host-fix/explore.md).
- [Implementación y marcadores de configuración](evidence/host-fix/implementation.md).
- [Verificación real del fix](evidence/host-fix/verification.md).
- [Review secuencial del agente anfitrión](evidence/host-fix/review.json).
- [Plan de feature pendiente de aprobación](feature-plan.md).
- [Protocolo para repetir en las herramientas externas](h05-protocol.md).

El fix observado cambia únicamente `number % 2 != 0` por `number % 2 == 0` en
app.py del laboratorio. Mensaje propuesto para su commit **local**:
`fix: sum even integers in H05 lab`. Ese commit no se ha creado ni publicado.

No se han utilizado `--approve-plan` ni `--approve-final` en la prueba anfitriona.
El plan pendiente añade count_even y sus pruebas, conserva sum_even y no toca las
pruebas base ni la configuración. Su aprobación debe ser posterior a leerlo.

Los siete tests nuevos de la herramienta de laboratorio son comprobaciones
deterministas; sus fixtures sintéticos no se usan como evidencia de aceptación real.
No cerrar H05 ni el recorrido conjunto de #2 con solo CI verde o este informe parcial.
