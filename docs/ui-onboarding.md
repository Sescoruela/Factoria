# UI interactiva y onboarding del MVP

## Objetivo

La entrada principal abre la interfaz web local. Este documento describe la TUI alternativa (`factoria tui`) y el onboarding de terminal, sin dependencias externas. No sustituye al CLI: lo hace más accesible y guía las decisiones que ya protege el núcleo de Factoria.

## Cómo abrirla

```bash
factoria
# o
factoria ui
```

La primera ejecución ofrece el onboarding. También puede repetirse en cualquier momento:

```bash
factoria onboarding
```

Al terminar el onboarding, Factoria continúa directamente al dashboard; no finaliza el proceso.

## Carpeta de proyectos

La UI permite elegir una carpeta raíz donde mantener organizados todos los proyectos. En Windows intenta abrir un selector nativo de carpeta; si no está disponible, pide la ruta por texto.

La preferencia se guarda localmente en:

```text
~/.factoria/ui.json
```

La configuración recuerda:

- la carpeta raíz de proyectos;
- el último repositorio seleccionado.

Factoria detecta todos los repositorios Git dentro de la carpeta raíz, también cuando están agrupados en subcarpetas. Durante el escaneo evita directorios generados pesados como `node_modules`, `.venv`, `bin`, `obj`, `dist` o `vendor`.

Desde **9. Gestionar proyectos** se puede:

- seleccionar un proyecto existente;
- crear un proyecto nuevo desde cero dentro de la carpeta raíz;
- cambiar la carpeta raíz de proyectos.

El selector no tiene un límite artificial de resultados. Muestra 10 proyectos por página para mantener la terminal legible, con navegación siguiente/anterior y búsqueda por nombre o ruta. La búsqueda se aplica sobre todos los proyectos encontrados.

### Crear un proyecto

La acción **Crear proyecto nuevo** pide nombre y descripción opcional. Antes de escribir nada muestra la ruta y pide confirmación explícita. Después:

1. crea la carpeta dentro de la raíz configurada;
2. ejecuta `git init -b main`;
3. crea un `README.md` inicial;
4. ofrece crear un commit `Initial commit` mediante una segunda confirmación;
5. selecciona automáticamente el proyecto recién creado;
6. ofrece preparar inmediatamente la memoria Factoria;
7. vuelve directamente al dashboard del nuevo proyecto, sin regresar al submenú de gestión.

Si se pospone la memoria, el dashboard muestra la acción **M. Inicializar memoria del proyecto** para continuar sin tener que salir de la TUI. Si el commit inicial falla por falta de `user.name` o `user.email`, el repositorio se conserva y la UI muestra el diagnóstico; no se borra el proyecto ya creado.

## Dashboard

La pantalla principal resume:

- carpeta raíz y proyecto seleccionado;
- proyecto y rama actual;
- working tree limpio o con cambios;
- memoria inicializada o pendiente;
- perfil efectivo y herramienta configurada;
- incidentes de secretos abiertos;
- flujo activo y runtime stage;
- siguiente recomendación operativa.

Si la memoria todavía no existe, la recomendación se presenta en lenguaje de UI y se ofrece la acción directa para inicializarla.

Si Git no está instalado o no está en `PATH`, el dashboard ya no falla con `WinError 2`: entra en modo diagnóstico, informa de que Git falta y mantiene disponibles la navegación, el onboarding y la selección de proyectos. Las operaciones que necesitan Git quedan bloqueadas con un mensaje explícito.

En `--read-only`, las opciones que modifican proyecto o estado del flujo no aparecen.

## Acciones guiadas

La UI permite:

1. consultar cómo iniciar una feature desde la herramienta externa;
2. consultar cómo iniciar un fix desde la herramienta externa;
3. consultar la reanudación desde la herramienta externa;
4. previsualizar y confirmar commits;
5. consultar historial;
6. revisar/resolver incidentes de seguridad;
7. repetir el onboarding;
8. actualizar el dashboard;
9. gestionar proyectos: seleccionar, crear o cambiar la carpeta raíz;
10. inicializar la memoria directamente cuando el proyecto aún no la tiene;
11. consultar la ayuda completa de comandos con `H`.

Cada acción reutiliza las mismas rutas gobernadas del CLI. La TUI no crea un segundo motor de ejecución ni relaja permisos.

## Modo comandos dentro de la TUI

El prompt principal acepta tanto las opciones del menú como comandos de Factoria. No es necesario cerrar el `.exe` ni abrir otra consola.

Por ejemplo:

```text
status
memoria-init --name Organizador --purpose "Organizar turnos por medias horas"
factoria history --limit 20
```

El prefijo `factoria` es opcional. Los argumentos entre comillas se conservan como una sola unidad, también en Windows.

La opción **H. Ver todos los comandos disponibles** muestra el catálogo de comandos y ejemplos de uso desde la propia UI. También se aceptan `help`, `ayuda` y `comandos`.

Los comandos escritos manualmente pasan por el mismo `entrypoint`, permisos, perfiles, confirmaciones y gates que el CLI normal. La consola interactiva no es una vía para saltarse seguridad.

## Onboarding

El onboarding tiene cinco pasos:

1. **Organización de proyectos**: elegir la carpeta raíz y, si ya existen repositorios, seleccionar uno.
2. **Modelo mental**: diferencia feature/fix, aprobaciones y límites de Git.
3. **Memoria**: explica `AGENTS.md` y permite ejecutar `memoria-init --yes` solo tras confirmación explícita y solo con un repositorio Git seleccionado.
4. **Herramientas**: comprueba Git y explica cómo iniciar/autenticar Codex/OpenCode fuera de la aplicación. No lanza sus diagnósticos.
5. **Primer flujo**: enseña rama, plan, review, commit, push y PR.

El estado de onboarding es una preferencia global de la aplicación y se guarda localmente en `~/.factoria/ui-state.json`. No se versiona dentro de los proyectos.

## Confirmaciones

La UI conserva los gates del núcleo:

- aprobar plan;
- aprobar resultado final;
- confirmar commit;
- confirmar creación de un proyecto y, por separado, su commit inicial;
- confirmar verificación manual cuando aplique;
- confirmar revisión de impacto externo cuando aplique;
- confirmar que un secreto fue rotado/revocado antes de resolver un incidente.

Push, PR, borrado de ramas y otras acciones fuera del alcance del MVP siguen sin automatizarse desde la TUI.

## Diseño deliberado

La interfaz web local sirve en loopback y requiere token de sesión para la API. Permite editar roles y flujos y preparar la integración de ambas herramientas. La TUI sigue disponible como alternativa. El uso directo desde Codex/OpenCode no requiere mantener ninguna de las interfaces abierta.

## Arranque externo de proveedores · 04/11/2026

La actualización del panel y el onboarding no ejecutan self-tests, ayuda, versionado ni configuración resuelta de Codex/OpenCode. Se guardan preferencias y rutas sin iniciar procesos. La API web y la consola de la TUI rechazan `feature`, `fix`, `resume` e `install`, que pueden iniciar proveedores; los flujos se solicitan desde la sesión externa. Las actualizaciones periódicas de la web no solapan solicitudes de estado.

Los próximos hitos de añadir/modificar/guardar recursos están en `editor-milestones.md`.
