# Orquestación de flujos de aplicación

Este hito introduce la capa de aplicación que coordina el dominio sin acoplarlo a Codex, OpenCode o GitHub.

## Responsabilidades

- Crear y gestionar ejecuciones de flujo.
- Persistir el estado mínimo necesario para `resume`.
- Mantener artefactos temporales bajo `.factoria/work/<flow_id>/`.
- Aplicar la regla de un único flujo incompleto por proyecto.
- Soportar `pause`, `resume`, `block`, `complete` y `cancel`.
- Limpiar artefactos temporales al completar o cancelar.
- Coordinar `memory-init` y `memory-update` con aprobación previa a escritura.

## Estado persistido

`state.toml` guarda únicamente lo necesario para recuperar el flujo:

- identificador;
- tipo;
- estado actual;
- etiqueta opcional;
- historial de transiciones con fecha y motivo.

No guarda código, secretos ni contexto completo del agente.

## Memoria

`MemoryInitFlow` reutiliza el inicializador existente y exige confirmación antes de escribir.

`MemoryUpdateFlow` separa tres pasos:

1. analizar la memoria actual;
2. presentar cambios con motivo y evidencia;
3. escribir solo después de confirmación explícita.

## Límites del hito

Todavía no se implementan los flujos funcionales `fix` y `feature`, la CLI, la integración Git real ni el sistema final de informes. Este hito deja la infraestructura necesaria para construirlos encima.
