# Hitos de edición de la factoría

Seguimiento: [issue #2](https://github.com/Sescoruela/Factoria/issues/2). Roadmap general: [issue #6](https://github.com/Sescoruela/Factoria/issues/6), `roadmap.md`.

La protección de guardado de workflows se aborda primero en H01 (#7); skills en H02 (#8), asignación de agentes en H03 (#9) y workflows nombrados en H04 (#10).

## Objetivo

Añadir, modificar y guardar skills, agentes y workflows desde Factoría. La aplicación
mantiene sus definiciones por proyecto y prepara los archivos que consumen Codex y
OpenCode. El usuario inicia y autentica esas herramientas por su cuenta, fuera de la
aplicación. Abrir, refrescar o configurar Factoría no debe arrancar ninguno de sus CLIs.

## Estado confirmado al 06/11/2026

- Corregido el diagnóstico de proveedores que se repetía al actualizar el panel.
- La web y la terminal de la aplicación permiten detección pasiva y guardar preferencias/rutas.
- El inicio, diagnóstico y reanudación de agentes se hacen desde herramientas externas.
- La web permite crear, modificar y guardar agentes propios y editar los cinco básicos, con control de conflictos y borradores.
- Las skills asignadas deben existir como archivos Markdown dentro del proyecto. La sección Skills permite crearlas, modificarlas, guardarlas y descartarlas.
- Los agentes se exportan al catálogo compartido para Codex/ChatGPT y a definiciones de OpenCode sin iniciar herramientas.
- Existe edición y guardado de los flujos fix/feature.
- El editor de agentes ofrece un selector de skills del catálogo y conserva las rutas Markdown anteriores.
- El diseñador permite asignar agentes personalizados a etapas con el mismo rol base. El diseñador también permite crear workflows con nombre propio basados en fix/feature.

Los nueve editores están implementados. El host con checkout completó fix y feature
con aprobaciones y commits locales; no acredita sesiones externas independientes.
La aceptación autenticada del recorrido completo sigue pendiente en H05.
Consultar [estado vigente](project-status.md) y [evidencia del host](acceptance/h05-status.md).

## Hitos

Esfuerzos orientativos de implementación y pruebas, sujetos al diseño del catálogo.

| ID | Elemento / acción | Estado | Entrega y beneficio | Esfuerzo | Dependencias | Criterio de aceptación |
| --- | --- | --- | --- | --- | --- | --- |
| SK-01 | Skills / añadir | Implementado; evidencia de cierre en H02 #8 | Crear una skill con identificador, nombre, descripción y contenido; reutilizar conocimiento propio | 0,5–1 día | Formato y ubicación del catálogo | Crear desde la UI y verla en la lista del proyecto; rechazar identificadores duplicados |
| SK-02 | Skills / modificar | Implementado; evidencia de cierre en H02 #8 | Abrir contenido existente y editarlo con indicador de cambios pendientes | 0,5–1 día | SK-01, SK-03 | Editar, descartar o guardar; conservar el resto de skills y avisar al cambiar de proyecto con cambios sin guardar |
| SK-03 | Skills / guardar | Implementado; evidencia de cierre en H02 #8 | Persistencia Markdown segura y regeneración de integración | 0,5–1 día | SK-01 | Cerrar/reabrir y recuperar exactamente el texto; detectar conflictos y no sobrescribir contenido ajeno; bloquear rutas externas y secretos detectables |
| AG-01 | Agentes / añadir | Implementado en PR #5 | Crear agentes propios basados en un rol, con instrucciones, skills y preferencias | 1–2 días | Skills Markdown existentes; base_role validado | Crear un agente distinto de los cinco básicos, asignarle skills existentes y mantenerlo tras reabrir |
| AG-02 | Agentes / modificar | Implementado; evidencia de cierre en H03 #9 | Editar agentes propios y básicos, referencias a skills y preferencias | 0,5–1 día | AG-01, AG-03 | Cambiar un agente, ver sus datos guardados y comprobar que se usan en el siguiente flujo preparado |
| AG-03 | Agentes / guardar | Implementado en PR #5 | Guardar el catálogo versionable con validación de referencias y conflictos | 0,5–1 día | AG-01 | Reabrir con el mismo catálogo; rechazar referencias inexistentes y no alterar snapshots de flujos iniciados |
| WF-01 | Workflows / añadir | Implementado; evidencia de cierre en H04 #10 | Crear workflows con nombre propio a partir de fix/feature y asignar agentes del catálogo | 1–2 días | AG-01, AG-03; contrato de workflows nombrados | Crear un flujo adicional y seleccionarlo explícitamente desde Codex y OpenCode tras preparar la integración |
| WF-02 | Workflows / modificar | Implementado; evidencia de cierre en H04 #10 | Editar etapas, agentes, perfiles y aprobaciones conservando los controles obligatorios | 1–2 días | WF-01, WF-03 | Modificar un flujo y usarlo en una ejecución nueva; bloquear un orden inválido y mantener intacto un flujo ya iniciado |
| WF-03 | Workflows / guardar | Implementado; evidencia de cierre en H04 #10 | Guardar workflows nombrados y regenerar sus recursos para ambas herramientas | 0,5–1 día | WF-01, integración por proyecto | Cerrar/reabrir y conservar el diseño; detectar errores antes de escribir; comprobar recursos generados para ambas herramientas |

## Orden propuesto

1. Entregado: catálogo y persistencia de skills: SK-01 → SK-03 → SK-02.
2. Entregado: catálogo de agentes personalizados, creación/edición/guardado; la asignación a etapas compatibles está implementada en H03.
3. Entregado: workflows nombrados: WF-01 → WF-03 → WF-02.
4. Pendiente de aceptación autenticada H05: crear skill → asignarla a agente → incluirlo en workflow → guardar
   → preparar proyecto → iniciar Codex/OpenCode externamente → ejecutar el flujo.

## Reglas comunes para los nueve hitos

- Mostrar guardado, cambios pendientes, errores y conflictos en la propia interfaz.
- Mantener los archivos compartidos versionables y los datos de máquina separados.
- Validar primero y escribir después; preservar lo existente ante un fallo de guardado.
- Avisar de integración desactualizada tras un cambio de definición.
- Mantener permisos, aprobaciones y verificaciones del flujo.
- No iniciar, autenticar ni diagnosticar Codex/OpenCode para crear o guardar recursos.
- Marcar un hito terminado solo con evidencia del recorrido de uso y sus pruebas.

## Decisiones del catálogo

- Identificadores estables y formatos anteriores compatibles; workflows nuevos de hasta 48 caracteres portables.
- Cada etapa conserva su rol y solo admite agentes de ese rol base.
- Los flujos propios se seleccionan explícitamente; las intenciones ambiguas se aclaran.
- Los cambios externos provocan conflicto y conservan el borrador. Las plantillas importables se entregan en H08; duplicar/archivar recursos sigue en H09. Ver [plantillas](project-templates.md).

## Agentes: uso y formato entregados

En **Agentes**, pulsa **Crear agente** o **Modificar**. El identificador es estable,
con hasta 64 caracteres: empieza por letra minúscula y admite números y guiones.
Cada agente propio tiene nombre y un rol base de los cinco existentes. Puedes
editar descripción, instrucciones, perfil, plataforma preferida y rutas de skills
existentes. El rol base de los cinco agentes básicos queda fijo.

**Guardar agente** valida antes de escribir `.factoria/agents.json` y conserva los
demás agentes. La escritura es atómica y usa una revisión del catálogo para rechazar
guardados atrasados; **Descartar / recargar** permite recuperar la versión actual.
Los errores conservan el borrador. La web avisa antes de abandonar cambios o cerrar
la página. Tras guardar, ve a **Integración** para preparar ambas herramientas.

El formato anterior sigue siendo válido. `role` es el identificador del catálogo;
`base_role` indica el rol de un agente propio. Se añaden `name` y `description`.
Los archivos preparados incluyen `.factoria/generated/agents.md`, el contexto de
ChatGPT y `.opencode/agents/factoria-<identificador>.md`. Los agentes propios se seleccionan explícitamente por etapa en el diseñador; el rol base y los controles del flujo se conservan.
La preferencia de modelo o plataforma no cambia la configuración de una sesión
externa ya abierta. Los permisos y snapshots de flujos existentes se conservan.

## Skills: uso y formato de H02

En **Skills**, usa **Crear skill**, **Modificar**, **Guardar skill** o **Descartar / recargar**.
El identificador es estable, en minúsculas, y el contenido se guarda en
`.factoria/skills/<identificador>.md`, con cabecera versionada que contiene nombre y descripción.
El cuerpo Markdown se recupera sin traducción de saltos de línea. No se sobrescriben
archivos ajenos ni se siguen enlaces simbólicos. Los identificadores reservados de Windows se rechazan.

La creación es exclusiva y el reemplazo atómico. Una revisión del catálogo detecta
modificaciones externas; errores y conflictos conservan el borrador. El cambio de
proyecto y el cierre de página avisan si hay cambios pendientes.

En **Agentes**, el selector **Añadir skill del catálogo** añade la ruta al agente.
Guarda el agente y prepara la integración: los archivos asignados se consultan desde
Codex y OpenCode, y el catálogo compartido vive en `.factoria/generated/skills.md`.
El contexto portable incluye el contenido; editar una skill desactualiza la integración.
Los archivos Markdown anteriores fuera del catálogo siguen siendo referencias válidas.
La asignación de agentes propios a etapas está implementada en H03; no confundir estos editores con la aceptación real en proveedores (H05).

## H03: agentes por etapa

En **Diseñador de flujo**, el selector **Agente de la etapa** muestra únicamente
agentes con rol base compatible. La opción predeterminada conserva el agente básico
del rol. Guarda el flujo y prepara la integración antes de iniciar una ejecución nueva.

El campo `role` de cada etapa permanece fijo y determina controles y permisos.
`agent_id` identifica al agente elegido; si falta o es null se usa el básico. El perfil
y la plataforma de la etapa prevalecen sobre las preferencias del agente. Las
instrucciones y skills son las del agente seleccionado. Una preferencia de plataforma
distinta requiere continuar explícitamente allí; no se inicia otra herramienta desde la UI.

Se rechazan identificadores inexistentes, roles incompatibles y cambios de rol base
de un agente referenciado. Desasigna primero al agente antes de cambiar su rol base.
Las revisiones de workflows incluyen la versión del catálogo de agentes. Las snapshots
antiguas sin `agent_id` siguen siendo válidas; las nuevas congelan selección, preferencias,
instrucciones y contenidos de skills, tanto en seguimiento nativo como en modo avanzado.

## H04: workflows con nombre propio

El selector del diseñador muestra todo el catálogo. **Crear a partir de** copia las
etapas y agentes de fix, feature o un workflow ya configurado. **Crear workflow**
abre un borrador con identificador, nombre y descripción. El identificador y el tipo
base quedan fijos tras guardar; el nombre, descripción y etapas compatibles son editables.

`.factoria/workflows.json` sigue siendo un objeto por identificador. Los básicos
conservan su formato; los propios añaden `id`, `name` y `description`, y mantienen
`kind` como tipo base. Guardar un recurso o preparar el proyecto conserva todos los demás.
Se mantiene la revisión de catálogo/proyecto, la escritura atómica y la conservación
de borradores ante errores; no se eliminan ni archivan recursos en este hito.

Tras preparar, usar `factoria native start <id> --tool <codex|opencode> --task "..."`,
`$factoria-<id>` o `/factoria-<id>`. `factoria project workflows` lista los identificadores.
Las guías y el catálogo `.factoria/generated/workflows.md` explican la selección.
Las snapshots guardan el identificador, nombre, tipo y definición originales; una
edición posterior no cambia el diseño congelado. Los estados antiguos sin
`workflow_id` conservan su interpretación fix/feature. H05 requiere aceptación real.
