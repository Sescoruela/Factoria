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

## Alcance actual

Los adaptadores se utilizan en el **modo orquestado** `factoria fix/feature`, que sí
puede iniciar etapas con agentes. El modo principal **directo**, preparado con
`factoria project prepare`, ejecuta el trabajo dentro de la sesión de Codex/OpenCode
y utiliza `factoria native` para seguimiento sin nuevas llamadas LLM.

- El enrutado orquestado exige un modelo concreto por perfil y valida capacidades.
- Codex se admite en solo lectura para el modo orquestado; OpenCode puede implementar
  bajo su configuración restrictiva. Ver `adapter-safety-verification.md`.
- En modo directo, el modelo y los permisos pertenecen a la sesión abierta. Los roles
  usan las instrucciones configuradas; no se simula selección de modelo ni aislamiento
  de subagentes. Una preferencia de plataforma distinta requiere continuar allí.
- Los self-tests no prueban autenticación ni disponibilidad de un modelo remoto.
- No se inventan métricas de tokens/coste si el proveedor no las devuelve.
