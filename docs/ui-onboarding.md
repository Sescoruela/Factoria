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

## Dashboard

La pantalla principal resume:

- proyecto y rama actual;
- working tree limpio o con cambios;
- memoria inicializada o pendiente;
- perfil efectivo y herramienta configurada;
- incidentes de secretos abiertos;
- flujo activo y runtime stage;
- siguiente recomendación operativa.

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
8. actualizar el dashboard.

Cada acción reutiliza las mismas rutas gobernadas del CLI. La TUI no crea un segundo motor de ejecución ni relaja permisos.

## Onboarding

El onboarding tiene cuatro pasos:

1. **Modelo mental**: diferencia feature/fix, aprobaciones y límites de Git.
2. **Memoria**: explica `AGENTS.md` y permite ejecutar `memoria-init --yes` solo tras confirmación explícita.
3. **Herramientas**: ofrece `install --check-only` para validar el entorno sin escribir configuración.
4. **Primer flujo**: enseña rama, plan, review, commit, push y PR.

Cuando termina, el estado de onboarding se guarda localmente en el metadata Git del repositorio (`.git/factoria/ui-state.json`). No se versiona. Si no se puede resolver el directorio Git, existe un fallback `.factoria/ui-state.json`, ignorado por Git.

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

No se usa una UI web en el MVP para evitar introducir servidor, autenticación, frontend y un segundo modelo de seguridad antes del dogfooding real. La TUI es portable entre Windows/macOS/Linux siempre que Python y Git estén disponibles.
