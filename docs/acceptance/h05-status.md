# H05 · Estado observado el 05/11/2026

**Parcial; no aceptado.** La prueba se realizó desde el agente anfitrión actual de
ChatGPT/Codex Work con checkout y shell, sobre repositorios sintéticos aislados.
No es una ejecución de Codex CLI ni de OpenCode ni una sesión nueva de descubrimiento.

| Entorno / caso | Resultado observado | Pendiente |
| --- | --- | --- |
| Codex CLI local / fix y feature | CLI ausente en este entorno | Instalación/sesión autenticada externa, versión/modelo y recorrido completo |
| OpenCode local / fix y feature | CLI ausente en este entorno | Instalación/sesión autenticada externa, versión/modelo y recorrido completo |
| Host actual con checkout / fix-lab | Agente y skill cargados; dos fallos iniciales; tres pruebas finales correctas; review registrada; commit local autorizado y flujo completado | Sesión nueva y ruta natural |
| Host actual con checkout / feature-lab | Plan aprobado; count_even implementado; siete pruebas y aceptación correctas; pausado en approve_final | Aprobación humana final, autorización del commit local y finish |
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
- [Plan de feature aprobado](feature-plan.md).
- [Cambios de la feature](evidence/host-feature/changes.diff), [verificación](evidence/host-feature/verification.md), [review](evidence/host-feature/review.json) y [propuesta de memoria](evidence/host-feature/memory-proposal.md).
- [Protocolo para repetir en las herramientas externas](h05-protocol.md).

El fix observado cambia únicamente `number % 2 != 0` por `number % 2 == 0` en
app.py del laboratorio. Commit **local**, autorizado por el usuario:
`891d923e520e55608749dbc33518bd876856cd84` (`fix: sum even integers in H05 lab`).
El flujo está completado, sin sesiones activas y con árbol limpio. El repositorio
sintético no tiene remotos; su código no se publica como código de Factoria.

El «Sí» posterior del usuario aprobó el plan de count_even y el commit local del fix.
Se utilizó `--approve-plan` para implementar la feature; no se ha utilizado
`--approve-final`. El avance sin aprobación final devuelve el error esperado y
el flujo está pausado en approve_final. Siete pruebas y acceptance_feature.py pasan;
sum_even, tests/test_app.py y acceptance_feature.py permanecen intactos.
La revisión es secuencial por el mismo agente anfitrión. La propuesta de memoria
no se aplica automáticamente. La feature todavía no tiene commit.

Los siete tests nuevos de la herramienta de laboratorio son comprobaciones
deterministas; sus fixtures sintéticos no se usan como evidencia de aceptación real.
No cerrar H05 ni el recorrido conjunto de #2 con solo CI verde o este informe parcial.
