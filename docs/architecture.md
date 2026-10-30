# Arquitectura inicial

## Principios

- El núcleo de Factoria es agnóstico de herramientas concretas como Codex, OpenCode o GitHub.
- Las integraciones externas se implementan mediante adaptadores y plugins.
- Los contratos del dominio priorizan tipado fuerte e inmutabilidad.
- Los flujos usan una máquina de estados explícita y auditable.
- Las acciones destructivas dependen del perfil de permisos (`safe`, `normal`, `power`).
- Los plugins pueden extender capacidades, pero las extensiones deben validarse antes de cargarse.
- El runtime objetivo es Python 3.11+ y el código de ejecución usa únicamente la biblioteca estándar.

## Capas

1. `domain`: contratos y reglas puras, sin dependencias externas.
2. `config`: lectura TOML, modelos inmutables y precedencia global → proyecto → ejecución.
3. `plugins`: manifest, compatibilidad, descubrimiento, prioridad, registro y carga de código confiable.
4. `application`: casos de uso y orquestación de flujos.
5. `infrastructure`: Git, persistencia, filesystem, ejecución de comandos y adaptadores.
6. `cli`: comandos directos y menú interactivo.

## Hito 1 — contratos de dominio

- `Flow` y su historial de transiciones.
- `FlowStateMachine` con transiciones explícitas.
- perfiles `safe`, `normal` y `power`.
- contratos `Adapter`, `Plugin`, `MemoryStore` y `CheckRunner`.
- modelos básicos de memoria y checks.

## Hito 2 — configuración y plugins

- configuración global y por proyecto en TOML;
- overrides temporales por ejecución;
- `max_agents = 2` por defecto y configurable;
- la herramienta por defecto vive fuera del proyecto;
- prioridad fija de plugins `personal > organization > builtin`;
- manifest obligatorio y versionado semántico;
- compatibilidad de plugins con Factoria;
- bloqueo de conflictos al mismo nivel de prioridad;
- trazabilidad de plugins eclipsados;
- estado `valid`, `warning` o `error`;
- carga de entrypoints Python después de validar y resolver el registro;
- tests con `unittest` y sin dependencias de runtime.

Los siguientes hitos añadirán memoria persistente del proyecto, flujos de aplicación, adaptadores concretos y CLI.
