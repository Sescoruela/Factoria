# UI interactiva y onboarding del MVP

## Objetivo

La UI del MVP es una TUI (terminal user interface) sin dependencias externas. No sustituye al CLI: lo hace más accesible y guía las decisiones que ya protege el núcleo de Factoria.

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

Factoria detecta como proyectos los repositorios Git ubicados directamente dentro de la carpeta raíz. Desde la opción **9. Cambiar proyecto / carpeta de proyectos** se puede cambiar de repositorio o modificar la carpeta raíz.

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

Si Git no está instalado o no está en `PATH`, el dashboard ya no falla con `WinError 2`: entra en modo diagnóstico, informa de que Git falta y mantiene disponibles la navegación, el onboarding y la selección de proyectos. Las operaciones que necesitan Git quedan bloqueadas con un mensaje explícito.

En `--read-only`, las opciones que modifican proyecto o estado del flujo no aparecen.

## Acciones guiadas

La UI permite:

1. iniciar una feature;
2. iniciar un fix;
3. reanudar y aprobar planes/resultados;
4. previsualizar y confirmar commits;
5. consultar historial;
6. revisar/resolver incidentes de seguridad;
7. repetir el onboarding;
8. actualizar el dashboard;
9. cambiar proyecto o carpeta raíz de proyectos.

Cada acción reutiliza las mismas rutas gobernadas del CLI. La TUI no crea un segundo motor de ejecución ni relaja permisos.

## Onboarding

El onboarding tiene cinco pasos:

1. **Organización de proyectos**: elegir la carpeta raíz y, si ya existen repositorios, seleccionar uno.
2. **Modelo mental**: diferencia feature/fix, aprobaciones y límites de Git.
3. **Memoria**: explica `AGENTS.md` y permite ejecutar `memoria-init --yes` solo tras confirmación explícita y solo con un repositorio Git seleccionado.
4. **Herramientas**: comprueba si Git está disponible y ofrece `install --check-only` para validar Codex/OpenCode.
5. **Primer flujo**: enseña rama, plan, review, commit, push y PR.

El estado de onboarding es una preferencia global de la aplicación y se guarda localmente en `~/.factoria/ui-state.json`. No se versiona dentro de los proyectos.

## Confirmaciones

La UI conserva los gates del núcleo:

- aprobar plan;
- aprobar resultado final;
- confirmar commit;
- confirmar verificación manual cuando aplique;
- confirmar revisión de impacto externo cuando aplique;
- confirmar que un secreto fue rotado/revocado antes de resolver un incidente.

Push, PR, borrado de ramas y otras acciones fuera del alcance del MVP siguen sin automatizarse desde la TUI.

## Diseño deliberado

No se usa una UI web en el MVP para evitar introducir servidor, autenticación, frontend y un segundo modelo de seguridad antes del dogfooding real. La TUI sigue siendo portable; el selector gráfico de carpeta es una mejora de UX y tiene fallback por ruta escrita.
