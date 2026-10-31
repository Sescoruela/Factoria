# Orquestación de agentes

Este hito conecta los adaptadores de herramientas con roles y perfiles abstractos de modelo sin acoplar el núcleo a Codex u OpenCode.

## Roles

- `explorer`: inspección del repositorio. Requiere acceso `read_only` explícitamente soportado por el adaptador/política.
- `planner`: genera planes y criterios de ejecución. Requiere `read_only` y salida estructurada.
- `implementer`: puede modificar el proyecto dentro del flujo autorizado.
- `reviewer`: revisa objetivo, criterios y reglas. Requiere `read_only` y salida estructurada.
- `documenter`: actualiza memoria del proyecto. Requiere una política explícita de `memory_write`.

El verificador no se modela como agente LLM: sigue usando `SafeCheckExecutor` y los comandos confirmados del proyecto.

## Perfiles de modelo

Los agentes piden perfiles abstractos:

- `rapido`
- `equilibrado`
- `potente`

`ModelRouter` resuelve cada perfil a un modelo concreto por adaptador. Factoria no incluye nombres de modelos codificados; cada entorno puede usar su propio mapa.

## Selección y fallback

`AgentOrchestrator`:

1. parte de la herramienta preferida, si existe;
2. valida disponibilidad, capacidades y política de acceso;
3. resuelve el modelo del perfil abstracto;
4. ejecuta el agente;
5. si falla y quedan intentos, prueba un adaptador compatible alternativo;
6. puede escalar `rapido -> equilibrado -> potente` según la política de reintentos.

Cada intento genera una traza con rol, adaptador, perfil, modelo, si hubo fallback y resultado. La traza no almacena el prompt ni el comando completo para evitar persistir información sensible innecesaria.

## Seguridad

Factoria no considera que una instrucción en el prompt sea una barrera de seguridad.

Los roles restringidos (`read_only` y `memory_write`) solo se pueden ejecutar cuando `AdapterSafetyPolicy` declara explícitamente que el adaptador soporta ese modo. Los argumentos concretos necesarios para activar la protección pertenecen a la configuración/política de cada entorno.

`project_write` es el modo base del implementador y sigue sujeto a las reglas del flujo, perfiles de permisos y restricciones de proyecto/organización.

## Flujos

`AgentWorkflowPlanner` define la secuencia de roles:

- fix pequeño: explorer -> implementer -> reviewer;
- fix grande: explorer -> planner -> implementer -> reviewer;
- feature: explorer -> planner -> implementer -> reviewer -> documenter.

La verificación automatizada se intercala fuera de este planner mediante la infraestructura de checks ya existente.

`FlowAgentCoordinator` puede ejecutar secuencialmente un workflow a partir de prompts por etapa y se detiene en el primer fallo.

## Límites actuales

- La política concreta para activar read-only/memory-write en Codex/OpenCode todavía debe configurarse por entorno.
- No se ejecutan push ni PR.
- Las métricas de tokens/coste se añadirán solo cuando el adaptador exponga datos fiables.
- El historial persistente de ejecución se conectará en un hito posterior.
