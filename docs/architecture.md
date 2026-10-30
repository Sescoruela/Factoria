# Arquitectura inicial

## Principios

- El núcleo de Factoria es agnóstico de herramientas concretas como Codex, OpenCode o GitHub.
- Las integraciones externas se implementan mediante adaptadores y plugins.
- Los contratos del dominio priorizan tipado fuerte e inmutabilidad.
- Los flujos usan una máquina de estados explícita y auditable.
- Las acciones destructivas dependen del perfil de permisos (`safe`, `normal`, `power`).
- Los plugins pueden extender capacidades, pero las extensiones de estado deben validarse antes de cargarse.

## Capas previstas

1. `domain`: contratos y reglas puras, sin dependencias externas.
2. `application`: casos de uso y orquestación de flujos.
3. `infrastructure`: Git, persistencia, filesystem, ejecución de comandos y adaptadores.
4. `cli`: comandos directos y menú interactivo.
5. `plugins`: descubrimiento, manifest, precedencia y carga.

## Primer hito

Este bootstrap cubre únicamente la base de dominio:

- `Flow` y su historial de transiciones.
- `FlowStateMachine` con transiciones explícitas.
- perfiles `safe`, `normal` y `power`.
- contratos `Adapter`, `Plugin`, `MemoryStore` y `CheckRunner`.
- modelos básicos de memoria, checks y manifest de plugins.
- tests unitarios de reglas críticas.

Los siguientes hitos añadirán configuración, persistencia de memoria, registro de plugins, flujos de aplicación y CLI.
