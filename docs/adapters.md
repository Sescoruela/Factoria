# Adaptadores de herramientas

Factoria mantiene el núcleo desacoplado de cualquier agente concreto. Los adaptadores traducen una solicitud neutral de agente a la CLI específica disponible en la máquina.

## Objetivos

- permitir Codex y OpenCode sin cambiar los flujos de dominio;
- detectar si el ejecutable está instalado antes de usarlo;
- ejecutar siempre con argumentos directos, sin `shell=True`;
- no relajar permisos de seguridad de la herramienta;
- permitir seleccionar modelo mediante una cadena neutral suministrada por la configuración;
- devolver un resultado normalizado con código de salida, stdout, stderr y error;
- exponer `self_test()` para comprobar disponibilidad/capacidades locales.

## Codex

El adaptador no interactivo usa `codex exec`. Cuando se solicita salida estructurada añade `--json`, que produce eventos JSONL en stdout. El modelo se pasa mediante `--model` cuando Factoria recibe uno explícitamente.

Factoria no añade automáticamente `--full-auto`, configuraciones de aprobación permisivas ni opciones equivalentes. La política de permisos debe permanecer bajo el control del entorno y del usuario.

## OpenCode

El adaptador no interactivo usa `opencode run`. El modelo se pasa mediante `--model` y, cuando se solicita salida estructurada, se usa `--format json`.

El directorio del proyecto se fija mediante `--dir` además del `cwd` local para que la intención sea explícita.

## Detección y fallback

`AdapterRegistry` mantiene los adaptadores disponibles y puede seleccionar el preferido. Si no está disponible, puede escoger el primer adaptador compatible configurado. La selección nunca cambia la política de permisos ni transforma una ejecución de solo lectura en una ejecución con escritura.

## Límites de este hito

- no se ejecutan agentes automáticamente desde `fix` o `feature` todavía;
- no se parsean métricas de tokens/coste específicas de proveedor;
- no se gestionan sesiones persistentes entre ejecuciones;
- el mapeo `rapido/equilibrado/potente -> modelo real` queda para la capa de configuración/orquestación;
- los self-tests comprueban instalación y ayuda/versionado, no autenticación completa contra el proveedor.
