# Integración directa por proyecto

## Objetivo y responsabilidades

Factoría configura y mantiene el sistema de trabajo del proyecto. Codex y OpenCode
son las interfaces principales para conversar con el LLM y trabajar sobre el código.
La configuración compartida se prepara para las dos herramientas desde el primer
uso; la aplicación web no necesita permanecer abierta.

| Componente | Responsabilidad |
| --- | --- |
| `.factoria/agents.json` | Roles, instrucciones, rutas de skills, perfil y plataforma preferida |
| `.factoria/workflows.json` | Etapas de fix/feature y preferencias por etapa |
| `.factoria/config.toml` | Políticas y flujos permitidos o bloqueados |
| `AGENTS.md`, `docs/memoria/` | Contexto y comandos confirmados del proyecto |
| `project prepare` | Validar y generar las integraciones compartidas |
| `native` | Estado local, evidencia, verificaciones, puntos de aprobación e historial |
| Codex/OpenCode | LLM, autenticación, permisos, edición y ejecución dentro de su sesión |

La configuración nueva es versionable. Si solo existen `ui-agents.json` o
`ui-workflows.json`, se leen como compatibilidad y se migran sin borrarlos al preparar
el proyecto. Una configuración mal formada bloquea; no se sustituye silenciosamente
por valores predeterminados. No se incluyen credenciales ni rutas personales de CLIs.

## Preparación

En la interfaz web: seleccionar proyecto → editar Agentes y Flujos → Integración →
Ver cambios → Preparar ambas herramientas. Guardar primero los cambios del editor.
Desde terminal, `factoria project prepare` muestra los archivos, `--yes` los genera
y `factoria project check` devuelve JSON con `ready`, cambios y conflictos.

Se generan:

- `.agents/skills/factoria-fix/SKILL.md` y `factoria-feature/SKILL.md`, descubribles por ambas herramientas.
- `.opencode/commands/factoria-fix.md` y `factoria-feature.md`, selección explícita en OpenCode.
- `.opencode/agents/factoria-<rol>.md`, subagentes OpenCode con lectura permitida y edición solicitada solo para implementación.
- `.factoria/generated/<identificador>.md`, instrucciones por workflow, incluidos fix/feature y los propios.
- `.factoria/generated/workflows.md`, catálogo e instrucciones de selección explícita.
- `.factoria/generated/chatgpt-context.md`, contexto portable para sesiones sin checkout.
- `.factoria/integration-manifest.json`, hashes y versión del formato generado.
- Un bloque delimitado en `AGENTS.md` para dirigir peticiones naturales a los flujos.

Los archivos existentes no gestionados producen conflicto. Los cambios propios de
`AGENTS.md` se conservan byte a byte fuera del bloque delimitado. No se sigue ningún
symlink de salida. Al deshabilitar un flujo se retiran únicamente sus archivos
generados cuyo contenido todavía coincide con el manifiesto. La regeneración se
revisa antes de escribir y nunca modifica la configuración global de las herramientas.

Después de cambiar agentes, flujos, skills o memoria, regenerar y revisar el diff.
`memoria-update` conserva el bloque de entrada de `AGENTS.md`; el contexto portable
queda pendiente de regeneración porque ha cambiado la memoria.

## Recorrido dentro de la herramienta

Guardar primero la configuración en Git y seleccionar una rama de trabajo limpia.
Abrir Codex/OpenCode en el proyecto y pedir «corrige este fallo». La instrucción de
entrada selecciona `factoria-fix`. La selección natural depende de que el agente
respete las instrucciones; la invocación explícita permite diagnosticar el enrutado:

- Codex: `$factoria-fix` o `$factoria-feature`.
- OpenCode: `/factoria-fix <petición>` o `/factoria-feature <petición>`.

La skill inicia `factoria native start fix --tool codex --task "<petición>"` (o
`opencode`). Este comando no inicia un proveedor LLM. Su JSON indica etapa, rol,
instrucciones, perfil, plataforma y archivo de evidencia. El agente realiza la etapa
y utiliza `factoria native next <id>` para avanzar. Los comandos admiten `--project`
antes del subcomando y localizan el repositorio desde una subcarpeta.

| Etapa | Evidencia o condición para avanzar |
| --- | --- |
| explore | `explore.md`, incluida reproducción comprobable en un fix |
| plan, si está configurada | `plan.md` con alcance y criterios verificables |
| approve_plan | Aprobación humana posterior, registrada con `--approve-plan`; plan y código sin cambios |
| implement | `implementation.md` y cambio dentro del alcance |
| verify, obligatoria | Comandos confirmados ejecutados por Factoría; si no existen, pasos manuales confirmados por el usuario con `--confirm-manual` |
| review | `review.json` con el contrato estructurado y sin hallazgos bloqueantes |
| document, si está configurada | Propuesta en `memory-proposal.md`, sin aplicación automática |
| approve_final, en feature/fix con plan | Aprobación humana posterior con `--approve-final` |
| ready_for_commit | Resumen y autorización de commit; push/PR manuales |
| finish | Árbol limpio y mismo contenido que fue verificado |

`native pause`/`resume` conservan etapa y evidencia. Un flujo incompleto, incluso
pausado, impide iniciar otro por los servicios comunes. `native cancel <id> --yes`
archiva el resultado y limpia solo los artefactos temporales; conserva código y rama.
No hay `stash`, reset ni borrado de ramas automático.

Una review bloqueante o cambios posteriores a la verificación requieren corregir y
usar `native retry`. Se repiten verificación y review, se archiva la revisión anterior
y se limita la corrección a dos ciclos y las verificaciones automatizadas a tres intentos. Los contratos con consumidores externos declarados requieren una confirmación humana separada con `--confirm-external-impact`; no se simula acceso a esos servicios. Los incidentes de secretos se mantienen
bloqueantes hasta resolverlos por la ruta de seguridad existente.

El flujo y los comandos confirmados se congelan al inicio. Las políticas actuales
siguen consultándose para que una nueva prohibición no se eluda con esa snapshot.
Las correcciones sin plan se limitan a 3 archivos/80 líneas con comprobaciones, o
2 archivos/40 líneas sin ellas; contratos declarados y configuraciones sensibles
requieren replantear con plan. El límite comprobable se aplica al avanzar: las
instrucciones piden detenerse antes de editar si ya se prevé ese alcance.

## Dos modos de ejecución

El modo directo conserva el control del LLM en la herramienta abierta. Los roles
pueden realizarse secuencialmente en esa sesión; no se promete aislamiento de modelos
ni cambio automático de LLM. Los subagentes OpenCode generados son recursos opcionales.
Si una etapa exige otra plataforma, se continúa allí el mismo flujo usando `--tool`.
La preferencia de perfil se muestra, pero la selección del modelo sigue perteneciendo
a Codex/OpenCode. Sus permisos y sandbox son la barrera de ejecución externa.

Desde una terminal externa, el modo avanzado `factoria fix/feature` sí inicia agentes mediante los adaptadores,
con su enrutado estricto, verificación de capacidades y permisos. Las instrucciones
y skills configuradas por rol también se incluyen en esos prompts y se congelan al
iniciar las ejecuciones nuevas. No llamar a ese modo desde la skill de uso directo:
crearía una segunda sesión LLM innecesaria.

## Codex en ChatGPT y conversación sin repositorio

Codex en un entorno con checkout puede consumir `AGENTS.md` y skills locales. La
disponibilidad del CLI de Factoría, Git y shell debe comprobarse en ese entorno.
No se integra con binarios privados de ChatGPT Desktop ni se supone que una
conversación normal puede leer una carpeta local.

Sin checkout: adjuntar `.factoria/generated/chatgpt-context.md` y el código necesario.
Sin herramientas, ChatGPT trabaja en modo propuesta y debe indicar las comprobaciones
pendientes. Ese documento puede contener arquitectura del proyecto: compartirlo solo
en el entorno apropiado. No incluye credenciales y la exportación usa el scanner
existente, cuya detección por patrones no garantiza encontrar cualquier secreto.

## Verificación reproducible

`python -m unittest discover -s tests` ejecuta pruebas de generación, migración,
conflictos, políticas, secretos, aprobaciones, fallos de verificación, estado e historial.
`test_project_integration.py` recorre fix/feature para ambos identificadores de
herramienta y usa también la CLI pública en repositorios temporales con espacios.
Estas pruebas no utilizan modelos remotos ni prueban que un LLM elija una skill.

Para aceptación real, repetir en Codex y OpenCode autenticados:

1. Preparar un repositorio de prueba desde la UI y guardar los archivos.
2. Cerrar Factoría y abrir la herramienta en el proyecto.
3. Pedir una corrección en lenguaje natural y confirmar qué skill/flujo ha cargado.
4. Completar el fix y verificar historial, evidencia y árbol limpio.
5. Pedir una feature y comprobar que espera aprobación del plan y resultado.
6. Probar una petición ambigua, una verificación fallida y un flujo deshabilitado.
7. En Codex/ChatGPT, comprobar el acceso al checkout y CLI; si faltan, verificar que
   informa del bloqueo en vez de simular ejecución.

Registrar versiones, plataforma, modelos, resultado y limitaciones en la lista de
cierre. No declarar esa aceptación superada a partir de las pruebas deterministas.

## Fuentes de formatos

- [OpenAI: instrucciones del proyecto](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
- [OpenAI: skills y descubrimiento local](https://learn.chatgpt.com/docs/build-skills).
- [OpenCode: skills](https://opencode.ai/docs/skills/).
- [OpenCode: comandos](https://opencode.ai/docs/commands/).
- [OpenCode: agentes](https://opencode.ai/docs/agents/).

## Aplicación sin inicio de proveedores

La web y la TUI solo muestran presencia pasiva y permiten guardar preferencias. No inician Codex/OpenCode ni ejecutan sus diagnósticos. Los endpoints y comandos internos que podrían lanzarlos se rechazan; abre la herramienta externa para trabajar o reanudar sus flujos.

## Workflows propios (H04)

Crear desde una plantilla en el diseñador y preparar la integración. Cada
identificador propio tiene `.agents/skills/factoria-<id>/SKILL.md` y
`.opencode/commands/factoria-<id>.md`. La selección explícita es
`factoria native start <id> --tool <codex|opencode> --task "..."`, o la skill/comando
correspondiente. Si la petición natural es ambigua entre varios workflows, pedir
aclaración antes de iniciar. No deducir un flujo propio por similitud de nombres.

El tipo base sigue determinando controles, permisos y aprobaciones. Bloquear fix
o feature también bloquea sus variantes; permitir un identificador no anula ese
bloqueo. Los flujos ya iniciados conservan la definición y metadatos originales.
El CLI de listado no llama a proveedores: `factoria project workflows`.
