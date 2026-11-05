# Hitos de edición de la factoría

Seguimiento: [issue #2](https://github.com/Sescoruela/Factoria/issues/2). Roadmap general: [issue #6](https://github.com/Sescoruela/Factoria/issues/6), `roadmap.md`.

La protección de guardado de workflows se aborda primero en H01 (#7); skills en H02 (#8), asignación de agentes en H03 (#9) y workflows nombrados en H04 (#10).

## Objetivo

Añadir, modificar y guardar skills, agentes y workflows desde Factoría. La aplicación
mantiene sus definiciones por proyecto y prepara los archivos que consumen Codex y
OpenCode. El usuario inicia y autentica esas herramientas por su cuenta, fuera de la
aplicación. Abrir, refrescar o configurar Factoría no debe arrancar ninguno de sus CLIs.

## Estado confirmado al 05/11/2026

- Corregido el diagnóstico de proveedores que se repetía al actualizar el panel.
- La web y la terminal de la aplicación permiten detección pasiva y guardar preferencias/rutas.
- El inicio, diagnóstico y reanudación de agentes se hacen desde herramientas externas.
- La web permite crear, modificar y guardar agentes propios y editar los cinco básicos, con control de conflictos y borradores.
- Las skills asignadas deben existir como archivos Markdown dentro del proyecto. Su editor sigue pendiente.
- Los agentes se exportan al catálogo compartido para Codex/ChatGPT y a definiciones de OpenCode sin iniciar herramientas.
- Existe edición y guardado de los flujos fix/feature.
- Las skills se referencian por ruta, pero todavía no tienen editor de creación/edición.
- La asignación de agentes personalizados a etapas y los workflows con nombre propio siguen pendientes.

Los hitos distinguen las funciones entregadas de la ampliación de skills y workflows pendiente.

## Hitos

Esfuerzos orientativos de implementación y pruebas, sujetos al diseño del catálogo.

| ID | Elemento / acción | Estado | Entrega y beneficio | Esfuerzo | Dependencias | Criterio de aceptación |
| --- | --- | --- | --- | --- | --- | --- |
| SK-01 | Skills / añadir | Pendiente | Crear una skill con identificador, nombre, descripción y contenido; reutilizar conocimiento propio | 0,5–1 día | Formato y ubicación del catálogo | Crear desde la UI y verla en la lista del proyecto; rechazar identificadores duplicados |
| SK-02 | Skills / modificar | Pendiente | Abrir contenido existente y editarlo con indicador de cambios pendientes | 0,5–1 día | SK-01, SK-03 | Editar, descartar o guardar; conservar el resto de skills y avisar al cambiar de proyecto con cambios sin guardar |
| SK-03 | Skills / guardar | Pendiente | Persistencia Markdown segura y regeneración de integración | 0,5–1 día | SK-01 | Cerrar/reabrir y recuperar exactamente el texto; detectar conflictos y no sobrescribir contenido ajeno; bloquear rutas externas y secretos detectables |
| AG-01 | Agentes / añadir | Completado | Crear agentes propios basados en un rol, con instrucciones, skills y preferencias | 1–2 días | Skills Markdown existentes; base_role validado | Crear un agente distinto de los cinco básicos, asignarle skills existentes y mantenerlo tras reabrir |
| AG-02 | Agentes / modificar | Parcial: editor completo; asignación a etapas pendiente en WF | Editar agentes propios y básicos, referencias a skills y preferencias | 0,5–1 día | AG-01, AG-03 | Cambiar un agente, ver sus datos guardados y comprobar que se usan en el siguiente flujo preparado |
| AG-03 | Agentes / guardar | Completado | Guardar el catálogo versionable con validación de referencias y conflictos | 0,5–1 día | AG-01 | Reabrir con el mismo catálogo; rechazar referencias inexistentes y no alterar snapshots de flujos iniciados |
| WF-01 | Workflows / añadir | Pendiente | Crear workflows con nombre propio a partir de fix/feature y asignar agentes del catálogo | 1–2 días | AG-01, AG-03; contrato de workflows nombrados | Crear un flujo adicional y seleccionarlo explícitamente desde Codex y OpenCode tras preparar la integración |
| WF-02 | Workflows / modificar | Parcial: editor fix/feature | Editar etapas, agentes, perfiles y aprobaciones conservando los controles obligatorios | 1–2 días | WF-01, WF-03 | Modificar un flujo y usarlo en una ejecución nueva; bloquear un orden inválido y mantener intacto un flujo ya iniciado |
| WF-03 | Workflows / guardar | Parcial: workflows.json actual | Guardar workflows nombrados y regenerar sus recursos para ambas herramientas | 0,5–1 día | WF-01, integración por proyecto | Cerrar/reabrir y conservar el diseño; detectar errores antes de escribir; comprobar recursos generados para ambas herramientas |

## Orden propuesto

1. Pendiente: catálogo y persistencia de skills: SK-01 → SK-03 → SK-02.
2. Entregado: catálogo de agentes personalizados, creación/edición/guardado; la asignación a etapas corresponde a WF.
3. Pendiente: workflows nombrados: WF-01 → WF-03 → WF-02.
4. Prueba completa: crear skill → asignarla a agente → incluirlo en workflow → guardar
   → preparar proyecto → iniciar Codex/OpenCode externamente → ejecutar el flujo.

## Reglas comunes para los nueve hitos

- Mostrar guardado, cambios pendientes, errores y conflictos en la propia interfaz.
- Mantener los archivos compartidos versionables y los datos de máquina separados.
- Validar primero y escribir después; preservar lo existente ante un fallo de guardado.
- Avisar de integración desactualizada tras un cambio de definición.
- Mantener permisos, aprobaciones y verificaciones del flujo.
- No iniciar, autenticar ni diagnosticar Codex/OpenCode para crear o guardar recursos.
- Marcar un hito terminado solo con evidencia del recorrido de uso y sus pruebas.

## Decisiones antes de ampliar el catálogo

- Formato de identificadores y compatibilidad con las definiciones actuales.
- Qué perfiles de agente pueden usarse en cada etapa sin debilitar los controles.
- Cómo seleccionar un workflow nombrado y resolver peticiones naturales ambiguas.
- Tratamiento de recursos importados y conflictos de edición externa.

Estas decisiones se cerrarán en la implementación del catálogo; no se presentan como
capacidades que ya estén disponibles.

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
ChatGPT y `.opencode/agents/factoria-<identificador>.md`. Los agentes propios están
disponibles explícitamente; no sustituyen automáticamente etapas de fix/feature.
La preferencia de modelo o plataforma no cambia la configuración de una sesión
externa ya abierta. Los permisos y snapshots de flujos existentes se conservan.
